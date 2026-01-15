-- Add embedding tables for chunk-level embeddings and headnote corpus

-- Assumes uuid-ossp and vector extensions already enabled in earlier migrations.

-- Chunk-level embeddings for court_cases using Cohere via Bedrock (1024-d)
CREATE TABLE IF NOT EXISTS case_embeddings_cohere (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES court_cases(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_type TEXT,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT case_embeddings_cohere_unique UNIQUE (case_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_case_embeddings_cohere_case_id
    ON case_embeddings_cohere(case_id);

CREATE INDEX IF NOT EXISTS idx_case_embeddings_cohere_vector
    ON case_embeddings_cohere
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Chunk-level embeddings for court_cases using Azure OpenAI (1536-d)
CREATE TABLE IF NOT EXISTS case_embeddings_openai (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES court_cases(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_type TEXT,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT case_embeddings_openai_unique UNIQUE (case_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_case_embeddings_openai_case_id
    ON case_embeddings_openai(case_id);

CREATE INDEX IF NOT EXISTS idx_case_embeddings_openai_vector
    ON case_embeddings_openai
    USING hnsw (embedding vector_cosine_ops);

-- Chunk-level embeddings for legislation_sections using Cohere via Bedrock (1024-d)
CREATE TABLE IF NOT EXISTS legislation_embeddings_cohere (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    section_id UUID NOT NULL REFERENCES legislation_sections(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_type TEXT,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legislation_embeddings_cohere_unique UNIQUE (section_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_cohere_section_id
    ON legislation_embeddings_cohere(section_id);

CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_cohere_vector
    ON legislation_embeddings_cohere
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Chunk-level embeddings for legislation_sections using Azure OpenAI (1536-d)
CREATE TABLE IF NOT EXISTS legislation_embeddings_openai (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    section_id UUID NOT NULL REFERENCES legislation_sections(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_type TEXT,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT legislation_embeddings_openai_unique UNIQUE (section_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_openai_section_id
    ON legislation_embeddings_openai(section_id);

CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_openai_vector
    ON legislation_embeddings_openai
    USING hnsw (embedding vector_cosine_ops);

-- Headnote corpus for dynamic few-shot examples
CREATE TABLE IF NOT EXISTS headnote_corpus (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    neutral_citation TEXT,
    court_code TEXT,
    subject_tags TEXT[],
    headnote_text TEXT NOT NULL,
    source TEXT,
    embedding_cohere VECTOR(1024),
    embedding_openai VECTOR(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_headnote_corpus_neutral_citation
    ON headnote_corpus(neutral_citation);

CREATE INDEX IF NOT EXISTS idx_headnote_corpus_embedding_cohere
    ON headnote_corpus
    USING ivfflat (embedding_cohere vector_cosine_ops) WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_headnote_corpus_embedding_openai
    ON headnote_corpus
    USING hnsw (embedding_openai vector_cosine_ops);
