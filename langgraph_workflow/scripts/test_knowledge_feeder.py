import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langgraph_agents.langgraph_system import EventBus, StateStore
from collab_agents.knowledge_feeder_agent import KnowledgeFeederAgent


async def main():
    eb = EventBus()
    ss = StateStore()
    agent = KnowledgeFeederAgent('knowledge_feeder', eb, ss, debug=True)

    files = [
        'data/docs/faq.txt',
        'data/docs/runbook.md',
        'data/docs/sampleword.docx',
        'data/docs/VeeamTags.docx',
    ]

    await ss.set('knowledge_files', files)
    res = await agent._execute_impl()
    print('\nKnowledge feeder result:', res)
    print('\nKnowledge ingestion state:', await ss.get('knowledge_ingestion_result'))


if __name__ == '__main__':
    asyncio.run(main())
