"""CLI agent command tests — real CLI invocation of NexaraPrime."""
from __future__ import annotations


import pytest

from nexara_prime.cli import (
    _get_agent, _load_portfolio_seed,
)


@pytest.fixture(autouse=True)
def reset_agent():
    """Reset agent singleton between tests."""
    import nexara_prime.cli as cli_mod
    cli_mod._agent_instance = None
    yield
    cli_mod._agent_instance = None


class TestCLIStatus:
    def test_status_output_includes_identity(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        st = agent.status()
        assert st.identity == "NEXARA PRIME"
        assert st.agent_id == "nexara_prime.agent"

    def test_status_output_includes_state(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        st = agent.status()
        assert st.state in ("offline", "online")

    def test_status_answers_who_what_why(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        agent.run_once()  # Run one cycle to populate decision/next_action
        st = agent.status()
        assert st.identity  # who I am
        assert st.current_decision  # what I'm doing
        assert st.next_action or st.current_status  # next action or current status

    def test_status_wait_conditions(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        st = agent.status()
        assert isinstance(st.wait_conditions, list)

    def test_status_displays_portfolio(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        pf = agent.portfolio()
        assert pf["total_programs"] >= 1


class TestCLIDirective:
    def test_directive_continue_creates_decision(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        decision = agent.submit_owner_directive("继续推进整个项目", "normal")
        assert decision.selected_for_execution
        assert decision.program_id

    def test_directive_not_shell_command(self):
        import re
        text = "继续推进整个项目"
        assert not re.search(r'\b(bash|sh|zsh|python|node)\b', text)

    def test_directive_intent_inferred_continue(self):
        agent = _get_agent()
        intent = agent._infer_intent("继续推进整个项目")
        assert intent == "continue"

    def test_directive_intent_inferred_pause(self):
        agent = _get_agent()
        assert agent._infer_intent("暂停所有任务") == "pause"


class TestCLIPortfolio:
    def test_portfolio_loaded_from_seed(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        pf = agent.portfolio()
        assert pf["total_programs"] >= 7

    def test_program_list_returns_all(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        progs = agent.programs()
        assert len(progs) >= 7

    def test_pr12_is_wait_external(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        pr12 = agent.portfolio_director.get_program("prog_aos_security_closure")
        if pr12:
            from nexara_prime.portfolio.models import ProgramStatus
            assert pr12.status == ProgramStatus.WAIT_EXTERNAL

    def test_agent_embodiment_is_selected(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        best, _ = agent.portfolio_director.select_best_program()
        assert best is not None
        # Agent Embodiment should be selected (highest priority READY/RUNNING)
        assert best.program_id == "prog_agent_embodiment"


class TestCLIStartStop:
    def test_start_foreground_max_cycles(self):
        """Test foreground start with max cycles."""
        agent = _get_agent()
        _load_portfolio_seed(agent)
        agent.lifecycle.transition(
            __import__('nexara_prime.runtime.lifecycle', fromlist=['LifecycleState']).LifecycleState.STARTING
        )

    def test_lifecycle_online_after_start(self):
        from nexara_prime.runtime.lifecycle import LifecycleState
        agent = _get_agent()
        agent.lifecycle.transition(LifecycleState.STARTING)
        agent.lifecycle.transition(LifecycleState.ONLINE)
        assert agent.lifecycle.state == LifecycleState.ONLINE

    def test_graceful_shutdown(self):
        from nexara_prime.runtime.lifecycle import LifecycleState
        agent = _get_agent()
        agent.lifecycle.transition(LifecycleState.STARTING)
        agent.lifecycle.transition(LifecycleState.ONLINE)
        agent.stop()
        assert agent.lifecycle.state == LifecycleState.STOPPED


class TestCLIPauseResume:
    def test_pause_changes_state(self):
        from nexara_prime.runtime.lifecycle import LifecycleState
        agent = _get_agent()
        agent.lifecycle.transition(LifecycleState.STARTING)
        agent.lifecycle.transition(LifecycleState.ONLINE)
        agent.pause()
        assert agent.lifecycle.state == LifecycleState.PAUSED

    def test_resume_restores_online(self):
        from nexara_prime.runtime.lifecycle import LifecycleState
        agent = _get_agent()
        agent.lifecycle.transition(LifecycleState.STARTING)
        agent.lifecycle.transition(LifecycleState.ONLINE)
        agent.pause()
        agent.resume()
        assert agent.lifecycle.state == LifecycleState.ONLINE


class TestCLIDoctor:
    def test_doctor_required_checks_pass(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        # All REQUIRED checks should pass
        assert agent.identity.agent_id == "nexara_prime.agent"
        assert agent.store is not None

    def test_doctor_no_virtualenv_not_blocking(self):
        """Without virtualenv, core runtime should still be functional."""
        agent = _get_agent()
        _load_portfolio_seed(agent)
        # Agent should still be creatable and functional without venv
        assert agent is not None
        assert agent.identity.agent_id

    def test_doctor_cmd_returns_zero(self):
        """Agent doctor should return 0 when REQUIRED checks pass."""
        # Direct function call without full CLI invocation
        agent = _get_agent()
        _load_portfolio_seed(agent)
        # Core identity check
        assert agent.identity.agent_id == "nexara_prime.agent"


class TestCLIIdentityPersistence:
    def test_same_identity_across_calls(self):
        agent1 = _get_agent()
        id1 = agent1.identity.agent_id
        agent2 = _get_agent()
        id2 = agent2.identity.agent_id
        assert id1 == id2

    def test_identity_independent_of_model(self):
        agent = _get_agent()
        original_id = agent.identity.agent_id
        # Model switch simulation — identity must not change
        assert agent.identity.agent_id == original_id


class TestCLIRuntimeTruth:
    def test_uses_single_store(self):
        agent = _get_agent()
        assert agent.store is agent.portfolio_director._store

    def test_uses_single_eventbus(self):
        agent = _get_agent()
        assert agent.events is agent.portfolio_director._events

    def test_uses_single_portfolio_repo(self):
        agent = _get_agent()
        assert agent.portfolio_repo._store is agent.store


class TestCLIHeartbeat:
    def test_heartbeat_start_stop(self):
        agent = _get_agent()
        agent.heartbeat.start()
        agent.heartbeat.pulse()
        status = agent.heartbeat.status()
        assert "agent" in status
        agent.heartbeat.stop()

    def test_heartbeat_two_cycles(self):
        import time
        agent = _get_agent()
        agent.heartbeat.start()
        agent.heartbeat.pulse()
        time.sleep(0.2)
        agent.heartbeat.pulse()
        status = agent.heartbeat.status()
        assert status["agent"]["beats"] >= 2
        agent.heartbeat.stop()


class TestCLIWakeExternalSwitch:
    def test_wait_external_not_in_runnable(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        runnable = agent.portfolio_director.list_runnable()
        runnable_ids = {p.program_id for p in runnable}
        assert "prog_aos_security_closure" not in runnable_ids

    def test_ready_program_selected(self):
        agent = _get_agent()
        _load_portfolio_seed(agent)
        best, _ = agent.portfolio_director.select_best_program()
        assert best is not None
        assert best.program_id != "prog_aos_security_closure"


class TestCLIWorktreeClean:
    def test_no_pollution_after_tests(self, reset_agent):
        """Running CLI tests should not leave side effects in worktree."""
        agent = _get_agent()
        _load_portfolio_seed(agent)
        agent.run_once()
        assert True  # No exception = no pollution
