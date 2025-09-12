#!/usr/bin/env python3
"""
Script to create new Milvus collection with configurable embedding dimension
"""
import sys
import logging
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType, utility
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_collection_with_dimension(collection_name=None, dimension=None, drop_if_exists=False):
    """
    Create a new Milvus collection with specified embedding dimension
    
    Args:
        collection_name: Name of the collection (defaults to settings)
        dimension: Embedding dimension (defaults to settings)
        drop_if_exists: Whether to drop existing collection
    """
    # Use defaults from settings if not provided
    collection_name = collection_name or settings.MILVUS_COLLECTION
    dimension = dimension or settings.EMBEDDING_DIMENSION
    
    try:
        # Connect to Milvus
        logger.info(f"Connecting to Milvus at {settings.MILVUS_HOST}:{settings.MILVUS_PORT}")
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=str(settings.MILVUS_PORT)
        )
        logger.info("✅ Connected to Milvus successfully")
        
        # Check if collection exists
        if utility.has_collection(collection_name):
            if drop_if_exists:
                logger.warning(f"⚠️ Collection '{collection_name}' exists. Dropping it...")
                utility.drop_collection(collection_name)
                logger.info(f"✅ Dropped existing collection '{collection_name}'")
            else:
                # Get existing collection info
                existing_collection = Collection(collection_name)
                existing_schema = existing_collection.schema
                
                # Find embedding field dimension
                for field in existing_schema.fields:
                    if field.name == "embedding":
                        existing_dim = field.params.get('dim', 'unknown')
                        logger.error(f"❌ Collection '{collection_name}' already exists with embedding dimension: {existing_dim}")
                        logger.info(f"   To create a new collection, either:")
                        logger.info(f"   1. Use a different collection name")
                        logger.info(f"   2. Run with --drop flag to replace existing collection")
                        logger.info(f"   3. Change MILVUS_COLLECTION in .env file")
                        return False
        
        # Define schema for new collection
        logger.info(f"Creating collection '{collection_name}' with embedding dimension: {dimension}")
        
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension),
            FieldSchema(name="metadata", dtype=DataType.JSON)
        ]
        
        schema = CollectionSchema(
            fields=fields,
            description=f"RAG chunks with {dimension}-dimensional embeddings"
        )
        
        # Create collection
        collection = Collection(
            name=collection_name,
            schema=schema
        )
        logger.info(f"✅ Collection '{collection_name}' created successfully")
        
        # Create index for vector field
        logger.info("Creating index for embedding field...")
        index_params = {
            "metric_type": "IP",  # Inner Product for normalized vectors
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        logger.info("✅ Index created successfully")
        
        # Load collection
        collection.load()
        logger.info("✅ Collection loaded into memory")
        
        # Print collection info
        logger.info("\n📊 Collection Information:")
        logger.info(f"   Name: {collection_name}")
        logger.info(f"   Embedding Dimension: {dimension}")
        logger.info(f"   Number of Entities: {collection.num_entities}")
        logger.info(f"   Status: Ready for use")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error creating collection: {e}")
        return False
    finally:
        # Disconnect
        connections.disconnect("default")
        logger.info("\n🔌 Disconnected from Milvus")


def main():
    """Main function to handle command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create new Milvus collection with configurable embedding dimension")
    parser.add_argument("--name", type=str, help="Collection name (defaults to .env setting)")
    parser.add_argument("--dimension", type=int, help="Embedding dimension (defaults to .env setting)")
    parser.add_argument("--drop", action="store_true", help="Drop existing collection if it exists")
    
    args = parser.parse_args()
    
    # Show current configuration
    logger.info("🔧 Configuration:")
    logger.info(f"   Collection Name: {args.name or settings.MILVUS_COLLECTION}")
    logger.info(f"   Embedding Dimension: {args.dimension or settings.EMBEDDING_DIMENSION}")
    logger.info(f"   Embedding Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"   Drop if Exists: {args.drop}")
    logger.info("")
    
    # Create collection
    success = create_collection_with_dimension(
        collection_name=args.name,
        dimension=args.dimension,
        drop_if_exists=args.drop
    )
    
    if success:
        logger.info("\n✨ Collection creation completed successfully!")
        logger.info("\n📝 Next Steps:")
        logger.info("   1. Your new collection is ready to use")
        logger.info("   2. Start ingesting documents with the new embedding dimension")
        logger.info("   3. Update MILVUS_COLLECTION in .env if you used a custom name")
    else:
        logger.error("\n❌ Collection creation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()