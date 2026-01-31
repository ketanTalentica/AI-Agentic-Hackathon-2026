import asyncio
import sys
from pathlib import Path

# Ensure the langgraph_workflow package root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from langgraph_agents.langgraph_system import EventBus, StateStore
from collab_agents.retrieval_agent import RetrievalAgent


async def main():
    eb = EventBus()
    ss = StateStore()
    agent = RetrievalAgent('retrieval_agent', eb, ss, debug=True)
    await ss.set('user_input', {'user_input': 'Veeam backup tags'})
    res = await agent._execute_impl()
    print('\nAgent result:', res)
    ctx = await ss.get('retrieved_context')
    print('\nRetrieved context (top results):')
    if isinstance(ctx, list):
        for i, r in enumerate(ctx, 1):
            print(f"\n[{i}] id={r.get('id')} score={r.get('score')}")
            print('metadata=', r.get('metadata'))
            print('snippet=', (r.get('snippet') or '')[:400])
    else:
        print(ctx)


if __name__ == '__main__':
    asyncio.run(main())
