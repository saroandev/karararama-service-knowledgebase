-- Initial database schema for conversation logs
-- This file is executed automatically when PostgreSQL container starts

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Conversation logs table
CREATE TABLE IF NOT EXISTS conversation_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    organization_id VARCHAR(255) NOT NULL,

    -- Message details
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,

    -- Context metadata
    sources JSONB DEFAULT '[]'::jsonb,  -- Sources used for this message
    tokens_used INTEGER DEFAULT 0,
    processing_time FLOAT DEFAULT 0.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Indexes
    CONSTRAINT check_role CHECK (role IN ('user', 'assistant', 'system'))
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_conversation_id ON conversation_log(conversation_id);
CREATE INDEX IF NOT EXISTS idx_user_id ON conversation_log(user_id);
CREATE INDEX IF NOT EXISTS idx_org_id ON conversation_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_created_at ON conversation_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversation_user ON conversation_log(conversation_id, user_id);

-- Create a composite index for multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_user_org_created ON conversation_log(user_id, organization_id, created_at DESC);

COMMENT ON TABLE conversation_log IS 'Stores chat conversation history for RAG system with multi-tenant support';
COMMENT ON COLUMN conversation_log.conversation_id IS 'Groups messages into a single conversation thread';
COMMENT ON COLUMN conversation_log.role IS 'Message sender role: user (human), assistant (AI), or system';
COMMENT ON COLUMN conversation_log.sources IS 'JSON array of source documents used for generating assistant response';
