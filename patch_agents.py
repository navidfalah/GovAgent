import os
import re

agent_files = [
    "risk_agent.py",
    "technical_agent.py",
    "security_agent.py",
    "privacy_agent.py",
    "bias_agent.py",
    "ethics_agent.py",
    "guardrail_agent.py",
    "policy_agent.py",
    "compliance_agent.py",
    "governance_agent.py"
]

for filename in agent_files:
    filepath = f"govagents/agents/{filename}"
    if not os.path.exists(filepath): continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # 1. Update imports
    if "Callable" not in content:
        content = content.replace("from typing import Any", "from typing import Any, Callable")
        if "from typing import Callable" not in content and "from typing import Any, Callable" not in content:
            if "from typing import " in content:
                content = re.sub(r'from typing import (.*)', r'from typing import Callable, \1', content, count=1)
            else:
                content = "from typing import Callable\n" + content
    
    # 2. Update run signature
    content = re.sub(
        r'async def run\(self, context: AgentContext\) -> ([a-zA-Z]+):',
        r'async def run(self, context: AgentContext, emit_callback: Callable = None) -> \1:',
        content
    )
    
    # 3. Add research call for non-coordinator/special agents
    if filename not in ["governance_agent.py", "policy_agent.py", "guardrail_agent.py", "compliance_agent.py"]:
        if "self._build_messages(user_prompt)" in content:
            research_injection = """
        # --- Sub-Agent Planning & Research ---
        research_results = await self._plan_and_research(context, user_prompt, emit_callback)
        if research_results:
            research_text = "Here is additional internet research gathered by your sub-agents:\\n\\n"
            for r in research_results:
                research_text += f"- Query: {r.query}\\n  Certainty: {r.certainty_score}\\n  Findings: {' '.join(r.findings)}\\n\\n"
            user_prompt += f"\\n\\n{research_text}"
        # ------------------------------------
"""
            content = content.replace(
                "        self.log.info(",
                research_injection + "        self.log.info("
            )
            
            # 4. Save research to output
            if f"{filename.split('_')[0].capitalize()}AgentOutput(" in content:
                content = content.replace(
                    f"{filename.split('_')[0].capitalize()}AgentOutput(",
                    f"{filename.split('_')[0].capitalize()}AgentOutput(\n            research=research_results,"
                )

    with open(filepath, 'w') as f:
        f.write(content)

print("Agents patched.")
