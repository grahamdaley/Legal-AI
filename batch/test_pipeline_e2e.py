"""End-to-end test of chunking, embeddings, and headnote generation.

This script:
1. Fetches a small number of cases from the database
2. Chunks the case text
3. Generates embeddings using Amazon Titan (Bedrock)
4. Generates a headnote using Azure OpenAI GPT-4o-mini
5. Displays results

Usage:
    python test_pipeline_e2e.py --limit 2
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent))

import asyncpg
import structlog

from config.settings import get_settings
from pipeline.chunking import chunk_case_text
from pipeline.embeddings import BedrockCohereBackend
from pipeline.summarizer import generate_headnote

logger = structlog.get_logger(__name__)


async def get_db_connection() -> asyncpg.Connection:
    """Connect to the database."""
    settings = get_settings()
    return await asyncpg.connect(settings.supabase_db_url)


async def fetch_test_cases(conn: asyncpg.Connection, limit: int = 2):
    """Fetch a small number of cases for testing."""
    rows = await conn.fetch(
        """
        SELECT id::text, neutral_citation, case_name, full_text, court_code
        FROM court_cases
        WHERE full_text IS NOT NULL
        ORDER BY created_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [dict(row) for row in rows]


async def test_chunking(case_id: str, full_text: str):
    """Test the chunking functionality."""
    print("\n" + "="*60)
    print("STEP 1: CHUNKING")
    print("="*60)
    
    chunks = chunk_case_text(case_id, full_text)
    
    print(f"✓ Created {len(chunks)} chunks")
    for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
        print(f"\nChunk {i}:")
        print(f"  Type: {chunk.chunk_type}")
        print(f"  Length: {len(chunk.text)} chars")
        print(f"  Text preview: {chunk.text[:150]}...")
        if chunk.paragraph_numbers:
            print(f"  Paragraph numbers: {chunk.paragraph_numbers[:5]}")
    
    if len(chunks) > 3:
        print(f"\n... and {len(chunks) - 3} more chunks")
    
    return chunks


async def test_embeddings(chunks):
    """Test the embedding generation."""
    print("\n" + "="*60)
    print("STEP 2: EMBEDDINGS")
    print("="*60)
    
    settings = get_settings()
    print(f"Using model: {settings.embedding_model}")
    print(f"AWS Region: {settings.aws_region}")
    
    # Test with just the first 2 chunks to save time
    test_chunks = chunks[:2]
    texts = [c.text for c in test_chunks]
    
    backend = BedrockCohereBackend(
        name="bedrock-titan",
        model_id=settings.embedding_model,
    )
    
    print(f"\nGenerating embeddings for {len(texts)} chunks...")
    embeddings = await backend.embed(texts)
    
    print(f"✓ Generated {len(embeddings)} embeddings")
    for i, emb in enumerate(embeddings):
        print(f"  Embedding {i}: {len(emb)} dimensions")
        print(f"    First 5 values: {emb[:5]}")
    
    return embeddings


async def test_headnote_generation(case_id: str):
    """Test headnote generation."""
    print("\n" + "="*60)
    print("STEP 3: HEADNOTE GENERATION")
    print("="*60)
    
    settings = get_settings()
    print(f"Using model: {settings.headnote_model}")
    
    print(f"\nGenerating headnote for case {case_id}...")
    headnote = await generate_headnote(case_id, max_chars=50000)
    
    if headnote:
        print(f"✓ Generated headnote ({len(headnote)} chars):\n")
        print("-" * 60)
        print(headnote)
        print("-" * 60)
    else:
        print("❌ Failed to generate headnote")
    
    return headnote


async def run_test(limit: int = 2):
    """Run the end-to-end test."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )
    
    log = logger.bind(component="test_pipeline_e2e")
    
    print("\n" + "="*60)
    print("LEGAL-AI PIPELINE END-TO-END TEST")
    print("="*60)
    
    conn = await get_db_connection()
    try:
        # Fetch test cases
        print("\nFetching test cases from database...")
        cases = await fetch_test_cases(conn, limit=limit)
        
        if not cases:
            print("❌ No cases found in database")
            return False
        
        print(f"✓ Found {len(cases)} cases")
        
        for idx, case in enumerate(cases, 1):
            print("\n" + "="*60)
            print(f"TESTING CASE {idx}/{len(cases)}")
            print("="*60)
            print(f"Case ID: {case['id']}")
            print(f"Citation: {case['neutral_citation'] or 'N/A'}")
            print(f"Name: {case['case_name']}")
            print(f"Text length: {len(case['full_text'])} chars")
            
            try:
                # Test chunking
                chunks = await test_chunking(case['id'], case['full_text'])
                
                # Test embeddings (only first 2 chunks to save time)
                embeddings = await test_embeddings(chunks)
                
                # Test headnote generation
                headnote = await test_headnote_generation(case['id'])
                
                if headnote:
                    print("\n✅ All pipeline steps completed successfully!")
                else:
                    print("\n⚠️  Pipeline completed but no headnote generated")
                
            except Exception as e:
                print(f"\n❌ Error testing case: {e}")
                log.exception("Test failed", case_id=case['id'], error=str(e))
                return False
        
        print("\n" + "="*60)
        print("TEST COMPLETE")
        print("="*60)
        return True
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Test the Legal-AI pipeline end-to-end"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=2,
        help="Number of cases to test (default: 2)",
    )
    args = parser.parse_args()
    
    success = asyncio.run(run_test(limit=args.limit))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
