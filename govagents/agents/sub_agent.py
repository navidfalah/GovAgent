import structlog
from duckduckgo_search import DDGS

from govagents.core.llm import get_llm_client
from govagents.core.models import ResearchReport
from govagents.core.logging import get_logger

log = get_logger(__name__)

class ResearchSubAgent:
    """A dynamic sub-agent that searches the live web and extracts structured findings."""
    
    def __init__(self, query: str):
        self.query = query
        self.llm = get_llm_client()
        
    async def run(self) -> ResearchReport:
        """Execute the search and extraction."""
        log.info("subagent_research_start", query=self.query)
        
        # 1. Search the web
        results = []
        try:
            # Run synchronous DDGS in a thread if needed, or just let it block since this is a prototype
            # Alternatively, we just do a quick loop
            ddgs = DDGS()
            for r in ddgs.text(self.query, max_results=3):
                results.append(r)
        except Exception as e:
            log.error("subagent_search_error", error=str(e), query=self.query)
            return ResearchReport(
                query=self.query, 
                findings=[f"Failed to execute search: {str(e)}"], 
                certainty_score=0.0
            )

        if not results:
            return ResearchReport(query=self.query, findings=["No results found."], certainty_score=0.0)

        # 2. Format search results for the LLM
        sources_text = "\n\n".join([f"Source: {r.get('href')}\nSnippet: {r.get('body')}" for r in results])
        urls = [r.get("href", "") for r in results if r.get("href")]

        # 3. Extract findings using LLM
        prompt = f"""You are a precise research assistant.
Based on the following search results for the query "{self.query}", extract the key findings.
Provide a certainty score between 0.0 and 1.0 based on how reliable and consistent the sources seem.

Search Results:
{sources_text}
"""
        
        try:
            report = await self.llm.structured_completion(
                prompt=prompt,
                schema=ResearchReport,
                system_prompt="Extract key findings and a certainty score from search snippets."
            )
            # Override with actual query and sources
            report.query = self.query
            report.sources = urls
            log.info("subagent_research_complete", query=self.query, certainty=report.certainty_score)
            return report
        except Exception as e:
            log.error("subagent_llm_error", error=str(e))
            return ResearchReport(
                query=self.query,
                findings=[f"Found results but failed to parse with LLM: {str(e)}"],
                certainty_score=0.1,
                sources=urls
            )
