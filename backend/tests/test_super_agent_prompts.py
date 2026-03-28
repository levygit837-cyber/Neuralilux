from app.super_agents.prompts import SUPER_AGENT_SYSTEM_PROMPT, TOOL_RESPONSE_SYSTEM_PROMPT


def test_super_agent_system_prompt_forces_brazilian_portuguese_thinking():
    assert "pense, gere o conteúdo de thinking e responda sempre em português do brasil" in SUPER_AGENT_SYSTEM_PROMPT.lower()
    assert "não use inglês no raciocínio nem na resposta final" in SUPER_AGENT_SYSTEM_PROMPT.lower()


def test_tool_response_prompt_keeps_thinking_in_brazilian_portuguese():
    assert "pense e escreva sempre em português do brasil" in TOOL_RESPONSE_SYSTEM_PROMPT.lower()
    assert "inclusive no conteúdo de thinking" in TOOL_RESPONSE_SYSTEM_PROMPT.lower()
    assert "responda de forma natural, humana e útil" in TOOL_RESPONSE_SYSTEM_PROMPT.lower()
    assert "não despeje json" in TOOL_RESPONSE_SYSTEM_PROMPT.lower()
