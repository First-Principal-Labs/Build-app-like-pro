from dataclasses import dataclass


@dataclass
class AgentConfig:
    """Runtime configuration for the orchestration agent."""

    base_dir: str = ""
    state_dir: str = "state"
    state_file: str = "agent_state.json"
    claude_timeout: int = 300
    code_gen_timeout: int = 600
    max_retries: int = 2
    auto_merge: bool = True
    squash_feature_merges: bool = True
    private_repo: bool = True
    log_level: str = "INFO"

    @property
    def state_filename(self) -> str:
        return f"{self.state_dir}/{self.state_file}"
