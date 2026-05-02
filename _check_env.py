# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

pkgs = ['chromadb', 'sentence_transformers', 'langchain', 'langgraph', 'rank_bm25', 'pymupdf', 'marker']
for pkg in pkgs:
    try:
        if pkg == 'chromadb':
            import chromadb
            print(f'{pkg}: {chromadb.__version__}')
        elif pkg == 'sentence_transformers':
            import sentence_transformers
            print(f'{pkg}: {sentence_transformers.__version__}')
        elif pkg == 'langchain':
            import langchain
            print(f'{pkg}: installed')
        elif pkg == 'langgraph':
            import langgraph
            print(f'{pkg}: installed')
        elif pkg == 'rank_bm25':
            import rank_bm25
            print(f'{pkg}: installed')
        elif pkg == 'pymupdf':
            import fitz
            print(f'pymupdf: installed')
        elif pkg == 'marker':
            import marker
            print(f'{pkg}: installed')
    except ImportError:
        print(f'{pkg}: NOT installed')
