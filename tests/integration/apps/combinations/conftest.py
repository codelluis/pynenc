from collections import namedtuple
from itertools import product
from typing import TYPE_CHECKING, Optional, Type

import pytest
from _pytest.monkeypatch import MonkeyPatch

from pynenc import Pynenc
from pynenc.arg_cache.base_arg_cache import BaseArgCache
from pynenc.broker.base_broker import BaseBroker
from pynenc.orchestrator.base_orchestrator import BaseOrchestrator
from pynenc.runner.base_runner import BaseRunner
from pynenc.serializer.base_serializer import BaseSerializer
from pynenc.state_backend.base_state_backend import BaseStateBackend
from tests import util
from tests.integration.apps.combinations import tasks

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest
    from _pytest.python import Metafunc

    from pynenc.task import Task


AppComponents = namedtuple(
    "AppComponents",
    [
        "arg_cache",
        "broker",
        "orchestrator",
        "runner",
        "serializer",
        "state_backend",
    ],
)


def get_combination_id(combination: AppComponents) -> str:
    return (
        f"run.{combination.runner.__name__.replace('Runner', '')}-"
        f"brk.{combination.broker.__name__.replace('Broker', '')}-"
        f"orc.{combination.orchestrator.__name__.replace('Orchestrator', '')}-"
        f"sbk.{combination.state_backend.__name__.replace('StateBackend', '')}-"
        f"ser.{combination.serializer.__name__.replace('Serializer', '')}-"
        f"arg.{combination.arg_cache.__name__.replace('ArgCache', '')}"
    )


def pytest_generate_tests(metafunc: "Metafunc") -> None:
    def get_subclasses(cls: type, mem_cls: Optional[bool] = None) -> list[type]:
        subclasses = []
        for c in cls.__subclasses__():
            if "mock" in c.__name__.lower() or c.__name__.startswith("Dummy"):
                continue
            if mem_cls is not None and mem_cls != c.__name__.startswith("Mem"):
                continue
            # if c.__name__.startswith("Process"):
            #     continue
            subclasses.append(c)
        return subclasses

    def get_runners(mem_compatible: bool) -> list[Type[BaseRunner]]:
        return [
            r
            for r in get_subclasses(BaseRunner)
            if r.mem_compatible() == mem_compatible  # type: ignore
        ]

    if "app" in metafunc.fixturenames:
        # These runners can run with any combination of components (including memory components)
        mem_compatible_runners_combinations = (
            AppComponents(*x)
            for x in product(
                get_subclasses(BaseArgCache),
                get_subclasses(BaseBroker),
                get_subclasses(BaseOrchestrator),
                get_runners(mem_compatible=True),
                get_subclasses(BaseSerializer),
                get_subclasses(BaseStateBackend),
            )
        )

        # These runner cannot be used with memory components
        # eg. ProcessRunner has different memory space for each task
        not_mem_compatible_runner_combinations = (
            AppComponents(*x)
            for x in product(
                get_subclasses(BaseArgCache, mem_cls=False),
                get_subclasses(BaseBroker, mem_cls=False),
                get_subclasses(BaseOrchestrator, mem_cls=False),
                get_runners(mem_compatible=False),
                get_subclasses(BaseSerializer, mem_cls=False),
                get_subclasses(BaseStateBackend, mem_cls=False),
            )
        )
        combinations = list(mem_compatible_runners_combinations) + list(
            not_mem_compatible_runner_combinations
        )
        ids = list(map(get_combination_id, combinations))
        metafunc.parametrize("app", combinations, ids=ids, indirect=True)


@pytest.fixture
def app(request: "FixtureRequest", monkeypatch: MonkeyPatch) -> Pynenc:
    components: AppComponents = request.param
    test_module, test_name = util.get_module_name(request)
    monkeypatch.setenv("PYNENC__APP_ID", f"{test_module}.{test_name}")
    monkeypatch.setenv("PYNENC__ORCHESTRATOR_CLS", components.orchestrator.__name__)
    monkeypatch.setenv("PYNENC__BROKER_CLS", components.broker.__name__)
    monkeypatch.setenv("PYNENC__SERIALIZER_CLS", components.serializer.__name__)
    monkeypatch.setenv("PYNENC__STATE_BACKEND_CLS", components.state_backend.__name__)
    monkeypatch.setenv("PYNENC__RUNNER_CLS", components.runner.__name__)
    monkeypatch.setenv("PYNENC__LOGGING_LEVEL", "debug")
    monkeypatch.setenv("PYNENC__ORCHESTRATOR__CYCLE_CONTROL", "True")
    # Set logging level before app initialization
    monkeypatch.setenv("PYNENC__LOGGING_LEVEL", "info")

    app = Pynenc()
    app.purge()
    request.addfinalizer(app.purge)
    return app


@pytest.fixture(scope="function")
def task_cycle(app: Pynenc) -> "Task":
    # this replacing the app of the task works in multithreading

    # but not in multi processing runner,
    # the process start from scratch and reference the function
    # with the mocked decorator
    tasks.cycle_start.app = app
    tasks.cycle_end.app = app
    return tasks.cycle_start


@pytest.fixture(scope="function")
def task_raise_exception(app: Pynenc) -> "Task":
    tasks.raise_exception.app = app
    return tasks.raise_exception


@pytest.fixture(scope="function")
def task_sum(app: Pynenc) -> "Task":
    tasks.sum.app = app
    return tasks.sum


@pytest.fixture(scope="function")
def task_get_text(app: Pynenc) -> "Task":
    tasks.get_text.app = app
    return tasks.get_text


@pytest.fixture(scope="function")
def task_get_upper(app: Pynenc) -> "Task":
    tasks.get_text.app = app
    tasks.get_upper.app = app
    return tasks.get_upper


@pytest.fixture(scope="function")
def task_direct_cycle(app: Pynenc) -> "Task":
    tasks.direct_cycle.app = app
    return tasks.direct_cycle


@pytest.fixture(scope="function")
def task_retry_once(app: Pynenc) -> "Task":
    tasks.retry_once.app = app
    return tasks.retry_once


@pytest.fixture(scope="function")
def task_sleep(app: Pynenc) -> "Task":
    tasks.sleep_seconds.app = app
    return tasks.sleep_seconds


@pytest.fixture(scope="function")
def task_cpu_intensive_no_conc(app: Pynenc) -> "Task":
    tasks.cpu_intensive_no_conc.app = app
    return tasks.cpu_intensive_no_conc
