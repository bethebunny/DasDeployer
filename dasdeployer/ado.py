# mypy: ignore-errors
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.released.build import Build, BuildClient, BuildDefinition

from dataclasses import dataclass
import enum
import threading
from github import Github
from typing import TYPE_CHECKING, Optional, Dict

if TYPE_CHECKING:
    from local_settings import ADOConfig


class QueryResultStatus(enum.Enum):
    CHECKING = "Checking"
    BUILD_COMPLETE = "Build Complete"
    BUILD_IN_PROGRESS = "Building"


class Environment(enum.Enum):
    DEV = "Dev"
    TEST = "Test"
    STAGE = "Stage"
    PROD = "Prod"


@dataclass
class Deployment:
    latest_build: Build
    deploying: bool
    branch: Optional[str] = None


@dataclass
class DeploymentStatus:
    deployments: dict[Environment, Deployment]


class AdoPipelines:
    def __init__(self, config: "ADOConfig"):
        self._poll_thread = None
        self.config = config

    def get_status(self) -> DeploymentStatus:
        if self._poll_thread is None:
            self._poll_thread = PollStatusThread(
                config=self.config, interval=10
            )
            self._poll_thread.start()
        return self._poll_thread._last_result

    def approve(self, env: str, params: Dict[str, str]) -> Optional[str]:
        print("Approve env:" + env)
        env = Environment(env)
        # Get Release Client
        connection = Connection(
            base_url=self.config.ado_org_url,
            creds=BasicAuthentication("", self.config.ado_pat),
        )
        build_client: BuildClient = connection.clients.get_build_client()

        build_def = build_client.get_definition(
            self.config.ado_project, self.config.ado_pipeline_ids[env.name]
        )

        status = self.get_status()
        deployment = status.deployments.get(env) if status else None
        branch = deployment.branch if deployment else None
        if not branch:
            return None

        build = Build(source_branch=branch, definition=build_def)
        build_result = build_client.queue_build(
            build=build, project=self.config.ado_project
        )
        return build_result.build_number


class PollStatusThread(threading.Thread):
    def __init__(self, config: "ADOConfig", interval=10):
        super(PollStatusThread, self).__init__()
        self.daemon = True
        self.stoprequest = threading.Event()

        self.delay = interval

        self.config = config

        self._connection = Connection(
            base_url=config.ado_org_url,
            creds=BasicAuthentication("", config.ado_pat),
        )
        self._build_client = self._connection.clients.get_build_client()

        self._last_result = None

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
                "PollStatusThread failed to die within %d seconds" % timeout
            )

    def run(self) -> None:
        while True:
            # Wait a bit then poll the server again
            github = Github(
                base_url=self.config.github_url,
                login_or_token=self.config.github_pat,
            )
            repo = github.get_repo(self.config.github_repo)
            branches = repo.get_branches()

            def newest(branches):
                return sorted(
                    branches,
                    key=lambda branch: branch.commit.commit.author.date,
                    reverse=True,
                )

            dev_branches = newest(
                branch for branch in branches if branch.name.startswith("dev/")
            )
            test_branches = newest(
                branch for branch in branches if branch.name.startswith("tst/")
            )
            main_branches = [
                branch for branch in branches if branch.name == "main"
            ]

            branches = {
                Environment.DEV: next(iter(dev_branches), None),
                Environment.TEST: next(iter(test_branches), None),
                Environment.STAGE: next(iter(main_branches), None),
                Environment.PROD: None,
            }

            deployments = {}

            for env, pipeline_id in self.config.ado_pipeline_ids.items():
                build_def: BuildDefinition = self._build_client.get_definition(
                    self.config.ado_project,
                    pipeline_id,
                    include_latest_builds=True,
                )
                env = Environment(env)
                deployments[Environment(env)] = Deployment(
                    latest_build=build_def.latest_build,
                    # Whether a build is in progress
                    deploying=build_def.latest_completed_build.id
                    != build_def.latest_build.id,
                    branch=branch.name if (branch := branches[env]) else None,
                )

            result = DeploymentStatus(deployments)

            if self._last_result != result:
                # Check if any values have changed to trigger saving a new result
                # the Build objects are not checked because they'll always be different
                # and we don't care of the Build changes unless one of these values
                # has changed
                print("change")
                self._last_result = result

            # At the end of the thread execution, wait a bit and then poll again
            if self.stoprequest.wait(self.delay):
                break
