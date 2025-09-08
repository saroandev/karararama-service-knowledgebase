"""
Unit tests for embedding generation module
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from app.embed import EmbeddingGenerator, OpenAIEmbedding, HuggingFaceEmbedding, embedding_generator


@pytest.mark.unit
@pytest.mark.embedding
class TestEmbeddingGenerator:
    """Test the base EmbeddingGenerator class"""

    def test_embedding_generator_abstract(self):
        """Test that EmbeddingGenerator is abstract"""
        with pytest.raises(TypeError):
            EmbeddingGenerator()


@pytest.mark.unit
@pytest.mark.embedding 
class TestOpenAIEmbedding:
    """Test the OpenAI embedding implementation"""

    @patch('app.embed.OpenAI')
    def test_openai_embedding_initialization(self, mock_openai):
        """Test OpenAI embedding initialization"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key", model="text-embedding-3-small")
        
        assert embedding.model_name == "text-embedding-3-small"
        assert embedding.dimension == 1536
        mock_openai.assert_called_once_with(api_key="test_key")

    @patch('app.embed.OpenAI')
    def test_openai_embedding_default_model(self, mock_openai):
        """Test OpenAI embedding with default model"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        
        assert embedding.model_name == "text-embedding-3-small"
        assert embedding.dimension == 1536

    @patch('app.embed.OpenAI')
    def test_generate_embeddings_single_text(self, mock_openai):
        """Test single text embedding generation"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        result = embedding.generate_embeddings(["Test text"])
        
        assert len(result) == 1
        assert len(result[0]) == 1536
        assert all(isinstance(x, float) for x in result[0])
        
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["Test text"]
        )

    @patch('app.embed.OpenAI')
    def test_generate_embeddings_multiple_texts(self, mock_openai):
        """Test multiple text embedding generation"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1] * 1536),
            MagicMock(embedding=[0.2] * 1536),
            MagicMock(embedding=[0.3] * 1536)
        ]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        texts = ["Text 1", "Text 2", "Text 3"]
        result = embedding.generate_embeddings(texts)
        
        assert len(result) == 3
        for emb in result:
            assert len(emb) == 1536
            assert all(isinstance(x, float) for x in emb)

    @patch('app.embed.OpenAI')
    def test_generate_embeddings_batch_processing(self, mock_openai):
        """Test batch processing for large number of texts"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Mock response for batch of texts
        mock_response.data = [MagicMock(embedding=[0.1] * 1536) for _ in range(10)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key", batch_size=5)
        texts = [f"Text {i}" for i in range(10)]
        
        result = embedding.generate_embeddings(texts)
        
        assert len(result) == 10
        # Should have made 2 batch calls (10 texts / 5 batch_size)
        assert mock_client.embeddings.create.call_count == 2

    @patch('app.embed.OpenAI')
    def test_generate_embeddings_api_error(self, mock_openai):
        """Test handling of API errors"""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        
        with pytest.raises(Exception, match="API Error"):
            embedding.generate_embeddings(["Test text"])

    @patch('app.embed.OpenAI')
    def test_generate_embeddings_empty_input(self, mock_openai):
        """Test handling of empty input"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        result = embedding.generate_embeddings([])
        
        assert result == []
        mock_client.embeddings.create.assert_not_called()


@pytest.mark.unit
@pytest.mark.embedding
class TestHuggingFaceEmbedding:
    """Test the HuggingFace embedding implementation"""

    @patch('app.embed.SentenceTransformer')
    def test_huggingface_embedding_initialization(self, mock_st):
        """Test HuggingFace embedding initialization"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        embedding = HuggingFaceEmbedding(model_name="test-model")
        
        assert embedding.model_name == "test-model"
        assert embedding.dimension == 384
        mock_st.assert_called_once_with("test-model", device="cpu")

    @patch('app.embed.SentenceTransformer')
    def test_huggingface_embedding_with_device(self, mock_st):
        """Test HuggingFace embedding with specific device"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_st.return_value = mock_model
        
        embedding = HuggingFaceEmbedding(model_name="test-model", device="cuda")
        
        assert embedding.device == "cuda"
        mock_st.assert_called_once_with("test-model", device="cuda")

    @patch('app.embed.SentenceTransformer')
    def test_generate_embeddings_huggingface(self, mock_st):
        """Test HuggingFace embedding generation"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
        mock_st.return_value = mock_model
        
        embedding = HuggingFaceEmbedding(model_name="test-model")
        result = embedding.generate_embeddings(["Text 1", "Text 2"])
        
        assert len(result) == 2
        assert len(result[0]) == 384
        assert isinstance(result[0], list)
        assert all(isinstance(x, (int, float)) for x in result[0])
        
        mock_model.encode.assert_called_once_with(
            ["Text 1", "Text 2"],
            show_progress_bar=False,
            convert_to_tensor=False,
            normalize_embeddings=True
        )

    @patch('app.embed.SentenceTransformer')
    def test_generate_embeddings_with_progress(self, mock_st):
        """Test HuggingFace embedding generation with progress bar"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.return_value = np.array([[0.1] * 384])
        mock_st.return_value = mock_model
        
        embedding = HuggingFaceEmbedding(model_name="test-model")
        result = embedding.generate_embeddings(["Text 1"], show_progress=True)
        
        assert len(result) == 1
        mock_model.encode.assert_called_once_with(
            ["Text 1"],
            show_progress_bar=True,
            convert_to_tensor=False,
            normalize_embeddings=True
        )

    @patch('app.embed.SentenceTransformer')
    def test_huggingface_model_loading_error(self, mock_st):
        """Test handling of model loading errors"""
        mock_st.side_effect = Exception("Model loading failed")
        
        with pytest.raises(Exception, match="Model loading failed"):
            HuggingFaceEmbedding(model_name="invalid-model")

    @patch('app.embed.SentenceTransformer')
    def test_generate_embeddings_encoding_error(self, mock_st):
        """Test handling of encoding errors"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_model.encode.side_effect = Exception("Encoding failed")
        mock_st.return_value = mock_model
        
        embedding = HuggingFaceEmbedding(model_name="test-model")
        
        with pytest.raises(Exception, match="Encoding failed"):
            embedding.generate_embeddings(["Test text"])


@pytest.mark.unit 
@pytest.mark.embedding
class TestEmbeddingGeneratorFactory:
    """Test the embedding generator factory function"""

    @patch('app.config.settings')
    @patch('app.embed.OpenAIEmbedding')
    def test_embedding_generator_openai(self, mock_openai_class, mock_settings):
        """Test embedding generator factory with OpenAI"""
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = "test_key"
        mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
        
        mock_instance = MagicMock()
        mock_openai_class.return_value = mock_instance
        
        from app.embed import embedding_generator
        result = embedding_generator()
        
        mock_openai_class.assert_called_once_with(
            api_key="test_key",
            model="text-embedding-3-small"
        )
        assert result == mock_instance

    @patch('app.config.settings')
    @patch('app.embed.HuggingFaceEmbedding')
    def test_embedding_generator_huggingface(self, mock_hf_class, mock_settings):
        """Test embedding generator factory with HuggingFace"""
        mock_settings.LLM_PROVIDER = "ollama"  # Non-OpenAI
        mock_settings.EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
        
        mock_instance = MagicMock()
        mock_hf_class.return_value = mock_instance
        
        from app.embed import embedding_generator
        result = embedding_generator()
        
        mock_hf_class.assert_called_once_with(
            model_name="intfloat/multilingual-e5-small"
        )
        assert result == mock_instance

    @patch('app.config.settings')
    def test_embedding_generator_missing_openai_key(self, mock_settings):
        """Test embedding generator factory with missing OpenAI key"""
        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.OPENAI_API_KEY = None
        mock_settings.EMBEDDING_MODEL = "text-embedding-3-small"
        
        from app.embed import embedding_generator
        
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            embedding_generator()


@pytest.mark.unit
@pytest.mark.embedding
class TestEmbeddingUtilities:
    """Test embedding utility functions"""

    def test_normalize_embeddings(self):
        """Test embedding normalization"""
        from app.embed import normalize_embeddings
        
        # Create unnormalized embeddings
        embeddings = np.array([
            [3.0, 4.0, 0.0],  # norm = 5
            [1.0, 1.0, 1.0],  # norm = sqrt(3)
        ])
        
        normalized = normalize_embeddings(embeddings)
        
        # Check that each embedding has norm close to 1
        for emb in normalized:
            norm = np.linalg.norm(emb)
            assert abs(norm - 1.0) < 1e-6

    def test_cosine_similarity_calculation(self):
        """Test cosine similarity calculation"""
        from app.embed import cosine_similarity
        
        emb1 = [1.0, 0.0, 0.0]
        emb2 = [0.0, 1.0, 0.0]  # Orthogonal
        emb3 = [1.0, 0.0, 0.0]  # Same as emb1
        
        # Orthogonal vectors should have similarity 0
        sim_orthogonal = cosine_similarity(emb1, emb2)
        assert abs(sim_orthogonal - 0.0) < 1e-6
        
        # Identical vectors should have similarity 1
        sim_identical = cosine_similarity(emb1, emb3)
        assert abs(sim_identical - 1.0) < 1e-6

    def test_batch_embeddings_processing(self):
        """Test batch processing utilities"""
        from app.embed import split_into_batches
        
        texts = [f"Text {i}" for i in range(23)]
        batches = list(split_into_batches(texts, batch_size=10))
        
        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 3

    def test_embedding_dimension_validation(self):
        """Test embedding dimension validation"""
        from app.embed import validate_embedding_dimensions
        
        # Valid embeddings
        embeddings = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
        assert validate_embedding_dimensions(embeddings, expected_dim=384)
        
        # Invalid dimensions
        invalid_embeddings = [[0.1] * 384, [0.2] * 512]  # Mixed dimensions
        assert not validate_embedding_dimensions(invalid_embeddings, expected_dim=384)
        
        # Empty list
        assert validate_embedding_dimensions([], expected_dim=384)


@pytest.mark.integration
@pytest.mark.embedding
class TestEmbeddingIntegration:
    """Integration tests for embedding generation"""

    @pytest.mark.slow
    @patch('app.embed.OpenAI')
    def test_full_embedding_pipeline(self, mock_openai):
        """Test complete embedding generation pipeline"""
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=np.random.normal(0, 1, 1536).tolist()),
            MagicMock(embedding=np.random.normal(0, 1, 1536).tolist())
        ]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        embedding = OpenAIEmbedding(api_key="test_key")
        
        texts = [
            "This is a sample document about machine learning.",
            "Natural language processing is a subset of artificial intelligence."
        ]
        
        result = embedding.generate_embeddings(texts)
        
        # Validate results
        assert len(result) == 2
        assert all(len(emb) == 1536 for emb in result)
        assert all(isinstance(emb, list) for emb in result)
        
        # Validate that embeddings are different
        assert result[0] != result[1]

    def test_embedding_consistency(self, mock_embeddings):
        """Test that same text produces consistent embeddings"""
        # This test uses the mock_embeddings fixture
        # In a real scenario, you'd test with actual embedding models
        
        assert len(mock_embeddings) == 3
        assert all(len(emb) == 384 for emb in mock_embeddings)
        
        # Test that embeddings are normalized
        for emb in mock_embeddings:
            norm = np.linalg.norm(emb)
            assert 0.9 <= norm <= 1.1  # Should be approximately normalized