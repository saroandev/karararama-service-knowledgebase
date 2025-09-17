"""
Generation and LLM schemas
"""

# LLM generation schemas
from schemas.generation.llm import (
    LLMProvider,
    LLMModel,
    LLMConfig,
    GenerationRequest,
    GenerationResponse,
    ChatMessage,
    ChatCompletionRequest,
    StreamChunk,
    BatchGenerationRequest,
    BatchGenerationResponse,
    LLMMetrics,
    LLMCache
)

# Prompt template schemas
from schemas.generation.prompt import (
    PromptType,
    PromptFormat,
    PromptTemplate,
    PromptInput,
    RenderedPrompt,
    FewShotExample,
    FewShotPrompt,
    ChainOfThoughtPrompt,
    PromptOptimization,
    PromptLibrary,
    PromptEvaluation,
    PromptVersion
)

__all__ = [
    # LLM
    "LLMProvider",
    "LLMModel",
    "LLMConfig",
    "GenerationRequest",
    "GenerationResponse",
    "ChatMessage",
    "ChatCompletionRequest",
    "StreamChunk",
    "BatchGenerationRequest",
    "BatchGenerationResponse",
    "LLMMetrics",
    "LLMCache",
    # Prompt
    "PromptType",
    "PromptFormat",
    "PromptTemplate",
    "PromptInput",
    "RenderedPrompt",
    "FewShotExample",
    "FewShotPrompt",
    "ChainOfThoughtPrompt",
    "PromptOptimization",
    "PromptLibrary",
    "PromptEvaluation",
    "PromptVersion",
]


# Helper functions
def create_llm_config(
    provider: str = "openai",
    model: str = None,
    api_key: str = None,
    temperature: float = 0.7
) -> LLMConfig:
    """
    Create LLM configuration

    Args:
        provider: LLM provider
        model: Model name
        api_key: API key
        temperature: Generation temperature

    Returns:
        LLMConfig
    """
    from schemas.generation.llm import LLMConfig, LLMProvider, LLMModel

    if not model:
        if provider == "openai":
            model = LLMModel.GPT_4O_MINI
        elif provider == "anthropic":
            model = LLMModel.CLAUDE_3_HAIKU
        else:
            model = "default"

    return LLMConfig(
        provider=LLMProvider(provider),
        model=model,
        api_key=api_key,
        temperature=temperature
    )


def create_prompt_template(
    name: str,
    template: str,
    prompt_type: str = "rag",
    variables: list = None
) -> PromptTemplate:
    """
    Create a prompt template

    Args:
        name: Template name
        template: Template string
        prompt_type: Type of prompt
        variables: Template variables

    Returns:
        PromptTemplate
    """
    from schemas.generation.prompt import PromptTemplate, PromptType

    return PromptTemplate(
        name=name,
        type=PromptType(prompt_type),
        template=template,
        variables=variables or []
    )


def render_prompt(
    template: PromptTemplate,
    variables: dict
) -> str:
    """
    Render a prompt template with variables

    Args:
        template: Prompt template
        variables: Variable values

    Returns:
        Rendered prompt string
    """
    prompt = template.template

    # Apply default values
    all_variables = template.default_values.copy()
    all_variables.update(variables)

    # Replace variables
    for var, value in all_variables.items():
        placeholder = "{" + var + "}"
        if placeholder in prompt:
            prompt = prompt.replace(placeholder, str(value))

    return prompt


def create_chat_message(
    role: str,
    content: str,
    name: str = None
) -> ChatMessage:
    """
    Create a chat message

    Args:
        role: Message role (system, user, assistant)
        content: Message content
        name: Optional sender name

    Returns:
        ChatMessage
    """
    from schemas.generation.llm import ChatMessage
    from datetime import datetime

    return ChatMessage(
        role=role,
        content=content,
        name=name,
        timestamp=datetime.now()
    )


def estimate_tokens(
    text: str,
    model: str = "gpt-4"
) -> int:
    """
    Estimate token count for text

    Args:
        text: Input text
        model: Model name for tokenizer

    Returns:
        Estimated token count
    """
    # Rough estimation: ~4 characters per token for English
    # For more accurate counting, use tiktoken or model-specific tokenizer
    return len(text) // 4


def calculate_generation_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str = "gpt-4o-mini"
) -> float:
    """
    Calculate generation cost

    Args:
        prompt_tokens: Input token count
        completion_tokens: Output token count
        model: Model name

    Returns:
        Estimated cost in USD
    """
    # Example pricing (update with actual prices)
    pricing = {
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},  # per 1K tokens
        "gpt-4o": {"input": 0.0025, "output": 0.01},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    }

    if model not in pricing:
        return 0.0

    input_cost = (prompt_tokens / 1000) * pricing[model]["input"]
    output_cost = (completion_tokens / 1000) * pricing[model]["output"]

    return input_cost + output_cost


def create_few_shot_prompt(
    task: str,
    examples: list,
    query: str
) -> str:
    """
    Create a few-shot prompt

    Args:
        task: Task description
        examples: List of input-output examples
        query: Query to complete

    Returns:
        Formatted few-shot prompt
    """
    prompt_parts = [task, ""]

    for i, example in enumerate(examples, 1):
        prompt_parts.append(f"Example {i}:")
        prompt_parts.append(f"Input: {example.get('input', '')}")
        prompt_parts.append(f"Output: {example.get('output', '')}")
        prompt_parts.append("")

    prompt_parts.append("Now, complete the following:")
    prompt_parts.append(f"Input: {query}")
    prompt_parts.append("Output:")

    return "\n".join(prompt_parts)


def create_rag_prompt(
    question: str,
    context: str,
    system_prompt: str = None
) -> dict:
    """
    Create a RAG prompt with context

    Args:
        question: User question
        context: Retrieved context
        system_prompt: Optional system prompt

    Returns:
        Dictionary with messages for chat completion
    """
    if not system_prompt:
        system_prompt = (
            "You are a helpful AI assistant. Answer the question based on the "
            "provided context. If the answer is not in the context, say so."
        )

    user_prompt = f"""Context:
{context}

Question: {question}

Please provide a comprehensive answer based on the context above."""

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }