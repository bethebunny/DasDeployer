# mypy: ignore-errors
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.released.build import Build, BuildClient, BuildDefinition

import threading
from github import Github
from operator import attrgetter
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from local_settings import ADOConfig


class QueryResultStatus():
    CHECKING = "Checking"
    BUILD_COMPLETE = "Build Complete"
    BUILD_IN_PROGRESS = "Building"


class QueryResult():
    def __init__(self):
        self.enable_dev = False
        self.enable_tst = False
        self.enable_stage = False
        self.enable_prod = False
        self.deploying_dev = False
        self.deploying_tst = False
        self.deploying_stage = False
        self.deploying_prod = False
        self.build_dev = None
        self.build_tst = None
        self.build_stage = None
        self.build_prod = None
        self.branch_dev = None
        self.branch_tst = None
        self.branch_stage = None
        self.branch_prod = None


class AdoPipelines():
    def __init__(
        self,
        config: "ADOConfig"

    ):
        self._poll_thread = None
        self.config = config

    def get_status(self):
        if self._poll_thread is None:
            self._poll_thread = PollStatusThread(
                config=self.config,
                interval=10
            )
            self._poll_thread.start()
        return self._poll_thread._last_result

    def approve(self, approve_env) -> Optional[str]:
        print("Approve env:" + approve_env)
        # Get Release Client
        connection = Connection(
            base_url=self.config.ado_org_url,
            creds=BasicAuthentication('', self.config.ado_pat)
        )
        build_client: BuildClient = connection.clients.get_build_client()

        build_def = build_client.get_definition(
            self.config.ado_project,
            self.config.ado_pipeline_ids[approve_env]
        )

        if approve_env == 'Dev':
            source_branch = self.get_status().branch_dev
        elif approve_env == 'Test':
            source_branch = self.get_status().branch_tst
        elif approve_env == 'Stage':
            source_branch = self.get_status().branch_stage
        elif approve_env == 'Prod':
            source_branch = self.get_status().branch_prod
        else:
            return None

        build = Build(
            source_branch=source_branch,
            definition=build_def
        )
        build_result = build_client.queue_build(
            build=build,
            project=self.config.ado_project
        )

        return build_result.build_number


class PollStatusThread(threading.Thread):
    def __init__(
        self,
        config: "ADOConfig",
        interval=10
    ):
        super(PollStatusThread, self).__init__()
        self.daemon = True
        self.stoprequest = threading.Event()

        # self.regularInterval = interval
        self.delay = interval

        self.config = config

        self._connection = Connection(
            base_url=config.ado_org_url,
            creds=BasicAuthentication('', config.ado_pat)
        )
        self._build_client = self._connection.clients.get_build_client()
        # self._rm_client = self._connection.clients.get_release_client()

        self._last_result = QueryResult()

    def start(self):
        self.stoprequest.clear()
        super(PollStatusThread, self).start()

    def stop(self, timeout=10) -> None:
        self.stoprequest.set()
        self.join(timeout)

    def join(self, timeout=None) -> None:
        super(PollStatusThread, self).join(timeout)
        if self.is_alive():
            assert timeout is not None
            raise RuntimeError(
                "PollStatusThread failed to die within %d seconds" % timeout)

    def run(self) -> None:
        while True:
            # Wait a bit then poll the server again
            result = QueryResult()
            github = Github(
                base_url=self.config.github_url,
                login_or_token=self.config.github_pat
            )
            repo = github.get_repo(self.config.github_repo)
            branches = repo.get_branches()

            dev_branches = [branch for branch in branches if branch.name.startswith('dev/')]
            dev_branches.sort(key=attrgetter('commit.commit.author.date'), reverse=True)
            dev_branch = dev_branches[0].name if dev_branches else None

            tst_branches = [branch for branch in branches if branch.name.startswith('tst/')]
            tst_branches.sort(key=attrgetter('commit.commit.author.date'), reverse=True)
            tst_branch = tst_branches[0].name if tst_branches else None

            main_branches = [branch for branch in branches if branch.name == 'main']
            main_branch = main_branches[0].name if main_branches else None

            for e in self.config.ado_pipeline_ids:
                buildDef: BuildDefinition = self._build_client.get_definition(
                    self.config.ado_project,
                    self.config.ado_pipeline_ids[e],
                    include_latest_builds=True
                )
                if buildDef.latest_completed_build.id == buildDef.latest_build.id:
                    # build is finished
                    deploying = False
                else:
                    # A build is in progress
                    deploying = True

                if e == 'Dev':
                    result.enable_dev = bool(dev_branch)
                    result.branch_dev = dev_branch
                    result.deploying_dev = deploying
                    result.build_dev = buildDef.latest_build

                elif e == 'Test':
                    result.enable_tst = bool(tst_branch)
                    result.branch_tst = tst_branch
                    result.deploying_tst = deploying
                    result.build_tst = buildDef.latest_build
                elif e == 'Stage':
                    result.enable_stage = bool(main_branch)
                    result.branch_stage = main_branch
                    result.deploying_stage = deploying
                    result.build_stage = buildDef.latest_build
                elif e == 'Prod':
                    result.enable_prod = True
                    result.branch_prod = None
                    result.deploying_prod = deploying
                    result.build_prod = buildDef.latest_build

            if (
                # Check if any values have changed to trigger saving a new result
                # the Build objects are not checked because they'll always be different
                # and we don't care of the Build changes unless one of these values
                # has changed
                self._last_result.enable_dev != result.enable_dev or
                self._last_result.enable_tst != result.enable_tst or
                self._last_result.enable_stage != result.enable_stage or
                self._last_result.enable_prod != result.enable_prod or
                self._last_result.deploying_dev != result.deploying_dev or
                self._last_result.deploying_tst != result.deploying_tst or
                self._last_result.deploying_stage != result.deploying_stage or
                self._last_result.deploying_prod != result.deploying_prod or
                self._last_result.branch_dev != result.branch_dev or
                self._last_result.branch_tst != result.branch_tst or
                self._last_result.branch_stage != result.branch_stage or
                self._last_result.branch_prod != result.branch_prod
            ):
                # Something has changed
                print("change")
                self._last_result = result

            # At the end of the thread execution, wait a bit and then poll again
            if self.stoprequest.wait(self.delay):
                break


# def pipemain():

#     # Create a connection to the org
#     connection = Connection(base_url=ORG_URL, creds=BasicAuthentication('', PAT))

#     # Get the build status
#     build_client: BuildClient = connection.clients.get_build_client()
#     # buildDef = build_client.get_definition(
#     #     PROJECT, BUILD_PIPELINE_ID, include_latest_builds=True
#     # )
#     build_def_dev = build_client.get_definition(
#         PROJECT, BUILD_PIPELINE_ID['Dev'], include_latest_builds=True
#     )
#     # build_def_tst = build_client.get_definition(
#     #     PROJECT, BUILD_PIPELINE_ID['Test'], include_latest_builds=True
#     # )
#     # build_def_stg = build_client.get_definition(
#     #     PROJECT, BUILD_PIPELINE_ID['Stage'], include_latest_builds=True
#     # )
#     build_def_prd = build_client.get_definition(
#         PROJECT, BUILD_PIPELINE_ID['Prod'], include_latest_builds=True
#     )

#     build = Build(
#         source_branch='dev/billing',
#         definition=build_def_dev,
#     )
#     build_result = build_client.queue_build(build=build, project=PROJECT)
#     print(build_result)

#     if build_def_prd.latest_completed_build.id == build_def_prd.latest_build.id:
#         print(
#             "Build " +
#             build_def_prd.latest_build.definition.name +
#             " " +
#             build_def_prd.latest_build.build_number +
#             " " +
#             build_def_prd.latest_completed_build.result
#         )
#     else:
#         # A build is in progress
#         print(
#             "Build " +
#             build_def_prd.latest_build.definition.name +
#             " " +
#             build_def_prd.latest_build.build_number +
#             " " +
#             build_def_prd.latest_completed_build.result +
#             " (" +
#             build_def_prd.latest_build.status +
#             ")"
#         )

    # Get Release Client
    # rm_client = connection.clients.get_release_client()

    # # See what environments we have and the status of their latest deployments
    # release = rm_client.get_release_definition(PROJECT, RELEASE_ID)
    # for e in release.environments:
    #     deployments = rm_client.get_deployments(
    #         PROJECT,
    #         definition_id=RELEASE_ID,
    #         definition_environment_id=e.id,
    #         top=1,
    #         deployment_status="all"
    #     )
    #     print(
    #         str(e.id) +
    #         " - " +
    #         e.name +
    #         ": " +
    #         deployments[0].release.name +
    #         " - " +
    #         deployments[0].deployment_status
    #     )

    # # Look up pending approvals
    # approvals = rm_client.get_approvals(project=PROJECT, type_filter="preDeploy")

    # for a in approvals:
    #     print(a.release.name + " awaiting approval to " + a.release_environment.name)

    # if len(approvals) > 0:
    #     # Approve one of them
    #     approval = approvals[0]
    #     approval.status = "approved"
    #     approval.comments = "Approved by DasDeployer"
    #     releaseApproval = rm_client.update_release_approval(approval, PROJECT, approval.id)
        # print(
        #     "Approved " +
        #     releaseApproval.release.name +
        #     " to " +
        #     releaseApproval.release_environment.name
        # )
