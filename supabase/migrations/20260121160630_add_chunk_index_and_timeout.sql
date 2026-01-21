-- Add composite indexes to speed up chunk_index = 0 filtering
-- and increase statement timeout for search operations

-- Add index on chunk_index for faster filtering
CREATE INDEX IF NOT EXISTS idx_case_embeddings_cohere_chunk_0 
    ON case_embeddings_cohere(case_id) 
    WHERE chunk_index = 0;

CREATE INDEX IF NOT EXISTS idx_legislation_embeddings_cohere_chunk_0 
    ON legislation_embeddings_cohere(section_id) 
    WHERE chunk_index = 0;

-- Increase statement timeout for RPC functions to 30 seconds
ALTER DATABASE postgres SET statement_timeout = '30s';

-- Also set it for the current session
SET statement_timeout = '30s';
