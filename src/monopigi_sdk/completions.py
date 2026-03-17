"""Shell completion helpers."""

COMPLETION_INSTRUCTIONS = {
    "bash": 'eval "$(monopigi --show-completion bash)"',
    "zsh": 'eval "$(monopigi --show-completion zsh)"',
    "fish": "monopigi --show-completion fish | source",
}


def get_completion_instructions(shell: str = "") -> str:
    """Get shell completion installation instructions."""
    if shell and shell in COMPLETION_INSTRUCTIONS:
        return f"Run: {COMPLETION_INSTRUCTIONS[shell]}"

    lines = ["Install shell completions:\n"]
    for sh, cmd in COMPLETION_INSTRUCTIONS.items():
        lines.append(f"  {sh}: {cmd}")
    return "\n".join(lines)
