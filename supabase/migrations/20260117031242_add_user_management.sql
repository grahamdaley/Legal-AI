-- User Management Schema for Legal AI
-- Implements user profiles, search history, and collections

-- =============================================================================
-- USER PROFILES
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    full_name TEXT,
    organization TEXT,
    subscription_tier TEXT DEFAULT 'free' CHECK (subscription_tier IN ('free', 'professional', 'enterprise')),
    search_quota_daily INT DEFAULT 50,
    searches_today INT DEFAULT 0,
    quota_reset_at TIMESTAMPTZ DEFAULT NOW(),
    preferences JSONB DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_subscription ON user_profiles(subscription_tier);

-- =============================================================================
-- USER SEARCHES (Search History)
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_searches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    search_type TEXT NOT NULL CHECK (search_type IN ('cases', 'legislation', 'all')),
    filters JSONB DEFAULT '{}'::JSONB,
    result_count INT DEFAULT 0,
    clicked_results UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_searches_user_id ON user_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_user_searches_created_at ON user_searches(created_at DESC);

-- =============================================================================
-- USER COLLECTIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_collections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES user_profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_collections_user_id ON user_collections(user_id);
CREATE INDEX IF NOT EXISTS idx_user_collections_is_public ON user_collections(is_public) WHERE is_public = TRUE;

-- =============================================================================
-- COLLECTION ITEMS
-- =============================================================================

CREATE TABLE IF NOT EXISTS collection_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    collection_id UUID NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL CHECK (item_type IN ('case', 'legislation')),
    item_id UUID NOT NULL,
    notes TEXT,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT collection_items_unique UNIQUE (collection_id, item_type, item_id)
);

CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id ON collection_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_item ON collection_items(item_type, item_id);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE collection_items ENABLE ROW LEVEL SECURITY;

-- User profiles: users can only access their own profile
CREATE POLICY "Users can view own profile" ON user_profiles
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own profile" ON user_profiles
    FOR UPDATE USING (auth.uid() = id);

-- Service role can manage all profiles
CREATE POLICY "Service role full access to profiles" ON user_profiles
    FOR ALL USING (auth.role() = 'service_role');

-- User searches: users can only access their own searches
CREATE POLICY "Users can view own searches" ON user_searches
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own searches" ON user_searches
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Service role full access to searches" ON user_searches
    FOR ALL USING (auth.role() = 'service_role');

-- User collections: users can access their own, and public collections
CREATE POLICY "Users can view own collections" ON user_collections
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can view public collections" ON user_collections
    FOR SELECT USING (is_public = TRUE);

CREATE POLICY "Users can insert own collections" ON user_collections
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own collections" ON user_collections
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own collections" ON user_collections
    FOR DELETE USING (auth.uid() = user_id);

CREATE POLICY "Service role full access to collections" ON user_collections
    FOR ALL USING (auth.role() = 'service_role');

-- Collection items: access follows collection access
CREATE POLICY "Users can view items in own collections" ON collection_items
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_collections 
            WHERE user_collections.id = collection_items.collection_id 
            AND user_collections.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can view items in public collections" ON collection_items
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_collections 
            WHERE user_collections.id = collection_items.collection_id 
            AND user_collections.is_public = TRUE
        )
    );

CREATE POLICY "Users can insert items in own collections" ON collection_items
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_collections 
            WHERE user_collections.id = collection_items.collection_id 
            AND user_collections.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete items in own collections" ON collection_items
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM user_collections 
            WHERE user_collections.id = collection_items.collection_id 
            AND user_collections.user_id = auth.uid()
        )
    );

CREATE POLICY "Service role full access to collection items" ON collection_items
    FOR ALL USING (auth.role() = 'service_role');

-- =============================================================================
-- AUTO-CREATE PROFILE ON USER SIGNUP
-- =============================================================================

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, full_name)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION handle_new_user();

-- =============================================================================
-- UPDATED_AT TRIGGERS
-- =============================================================================

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_collections_updated_at
    BEFORE UPDATE ON user_collections
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Function to check and decrement user's daily search quota
CREATE OR REPLACE FUNCTION check_and_decrement_quota(p_user_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_quota INT;
    v_used INT;
    v_reset_at TIMESTAMPTZ;
BEGIN
    SELECT search_quota_daily, searches_today, quota_reset_at
    INTO v_quota, v_used, v_reset_at
    FROM user_profiles
    WHERE id = p_user_id;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- Reset quota if it's a new day
    IF v_reset_at < CURRENT_DATE THEN
        UPDATE user_profiles
        SET searches_today = 1, quota_reset_at = NOW()
        WHERE id = p_user_id;
        RETURN TRUE;
    END IF;

    -- Check if quota exceeded
    IF v_used >= v_quota THEN
        RETURN FALSE;
    END IF;

    -- Increment usage
    UPDATE user_profiles
    SET searches_today = searches_today + 1
    WHERE id = p_user_id;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get user's remaining quota
CREATE OR REPLACE FUNCTION get_user_quota(p_user_id UUID)
RETURNS TABLE (
    daily_limit INT,
    used_today INT,
    remaining INT,
    resets_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        up.search_quota_daily AS daily_limit,
        CASE 
            WHEN up.quota_reset_at < CURRENT_DATE THEN 0
            ELSE up.searches_today
        END AS used_today,
        CASE 
            WHEN up.quota_reset_at < CURRENT_DATE THEN up.search_quota_daily
            ELSE GREATEST(0, up.search_quota_daily - up.searches_today)
        END AS remaining,
        CASE 
            WHEN up.quota_reset_at < CURRENT_DATE THEN (CURRENT_DATE + INTERVAL '1 day')::TIMESTAMPTZ
            ELSE (DATE(up.quota_reset_at) + INTERVAL '1 day')::TIMESTAMPTZ
        END AS resets_at
    FROM user_profiles up
    WHERE up.id = p_user_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE user_profiles IS 'User profile information and subscription details';
COMMENT ON TABLE user_searches IS 'Search history for analytics and personalization';
COMMENT ON TABLE user_collections IS 'User-created collections of saved cases and legislation';
COMMENT ON TABLE collection_items IS 'Items within user collections';
COMMENT ON FUNCTION check_and_decrement_quota IS 'Atomically check and decrement user search quota';
COMMENT ON FUNCTION get_user_quota IS 'Get user quota status including remaining searches';