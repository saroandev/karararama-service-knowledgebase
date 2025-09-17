"""
Prompt template and management schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


class PromptType(str, Enum):
    """Types of prompt templates"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    RAG = "rag"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    CHAT = "chat"
    COMPLETION = "completion"
    INSTRUCTION = "instruction"
    FEW_SHOT = "few_shot"


class PromptFormat(str, Enum):
    """Prompt formatting styles"""
    PLAIN = "plain"
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"
    JINJA2 = "jinja2"
    F_STRING = "f_string"


class PromptTemplate(BaseModel):
    """Prompt template definition"""
    name: str = Field(..., description="Template name")
    type: PromptType = Field(..., description="Template type")
    format: PromptFormat = Field(default=PromptFormat.PLAIN, description="Template format")

    # Template content
    template: str = Field(..., description="Template string")
    system_template: Optional[str] = Field(default=None, description="System prompt template")
    user_template: Optional[str] = Field(default=None, description="User prompt template")

    # Variables
    variables: List[str] = Field(default_factory=list, description="Template variables")
    required_variables: List[str] = Field(default_factory=list, description="Required variables")
    default_values: Dict[str, Any] = Field(default_factory=dict, description="Default variable values")

    # Metadata
    description: Optional[str] = Field(default=None, description="Template description")
    version: str = Field(default="1.0.0", description="Template version")
    tags: List[str] = Field(default_factory=list, description="Template tags")

    # Settings
    max_length: Optional[int] = Field(default=None, ge=1, description="Maximum prompt length")
    language: str = Field(default="en", description="Template language")

    # Usage tracking
    usage_count: int = Field(default=0, ge=0, description="Number of times used")
    last_used: Optional[datetime] = Field(default=None, description="Last usage timestamp")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")

    @validator("required_variables", always=True)
    def validate_required_variables(cls, v, values):
        """Ensure required variables are subset of all variables"""
        if "variables" in values:
            for req_var in v:
                if req_var not in values["variables"]:
                    raise ValueError(f"Required variable '{req_var}' not in variables list")
        return v

    @validator("variables", always=True)
    def extract_variables(cls, v, values):
        """Extract variables from template if not provided"""
        if not v and "template" in values:
            import re
            # Extract {variable} patterns
            pattern = r'\{([^}]+)\}'
            variables = re.findall(pattern, values["template"])
            return list(set(variables))
        return v

    class Config:
        use_enum_values = True
        validate_assignment = True


class PromptInput(BaseModel):
    """Input for prompt rendering"""
    template_name: Optional[str] = Field(default=None, description="Template name to use")
    template: Optional[PromptTemplate] = Field(default=None, description="Template object")

    # Variable values
    variables: Dict[str, Any] = Field(default_factory=dict, description="Variable values")

    # Context
    context: Optional[str] = Field(default=None, description="Additional context")
    chat_history: Optional[List[Dict[str, str]]] = Field(default=None, description="Chat history")

    # Options
    validate_required: bool = Field(default=True, description="Validate required variables")
    use_defaults: bool = Field(default=True, description="Use default values")
    truncate: bool = Field(default=False, description="Truncate if exceeds max length")

    @validator("template")
    def validate_template_source(cls, v, values):
        """Ensure either template_name or template is provided"""
        if not v and not values.get("template_name"):
            raise ValueError("Either template_name or template must be provided")
        return v

    class Config:
        validate_assignment = True


class RenderedPrompt(BaseModel):
    """Rendered prompt result"""
    prompt: str = Field(..., description="Rendered prompt text")
    system_prompt: Optional[str] = Field(default=None, description="Rendered system prompt")

    # Metadata
    template_name: Optional[str] = Field(default=None, description="Template used")
    variables_used: Dict[str, Any] = Field(default_factory=dict, description="Variables applied")

    # Statistics
    token_count: Optional[int] = Field(default=None, ge=0, description="Estimated token count")
    character_count: int = Field(..., ge=0, description="Character count")
    truncated: bool = Field(default=False, description="Whether prompt was truncated")

    # Validation
    missing_variables: List[str] = Field(default_factory=list, description="Missing required variables")
    warnings: List[str] = Field(default_factory=list, description="Rendering warnings")

    @validator("character_count", always=True)
    def calculate_character_count(cls, v, values):
        """Calculate character count"""
        if "prompt" in values:
            return len(values["prompt"])
        return v or 0

    class Config:
        validate_assignment = True


class FewShotExample(BaseModel):
    """Few-shot learning example"""
    input: str = Field(..., description="Example input")
    output: str = Field(..., description="Example output")

    # Optional fields
    explanation: Optional[str] = Field(default=None, description="Explanation of example")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Example metadata")

    # Quality
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Example quality")
    verified: bool = Field(default=False, description="Whether example is verified")

    class Config:
        validate_assignment = True


class FewShotPrompt(BaseModel):
    """Few-shot prompt configuration"""
    task_description: str = Field(..., description="Task description")
    examples: List[FewShotExample] = Field(..., min_items=1, description="Few-shot examples")

    # Formatting
    example_separator: str = Field(default="\n\n", description="Separator between examples")
    input_prefix: str = Field(default="Input: ", description="Prefix for input")
    output_prefix: str = Field(default="Output: ", description="Prefix for output")

    # Selection
    num_examples: Optional[int] = Field(default=None, ge=1, description="Number of examples to use")
    selection_strategy: Literal["random", "similarity", "diverse", "quality"] = Field(
        default="similarity",
        description="Example selection strategy"
    )

    # Options
    include_explanation: bool = Field(default=False, description="Include explanations")
    randomize_order: bool = Field(default=False, description="Randomize example order")

    @validator("num_examples")
    def validate_num_examples(cls, v, values):
        """Ensure num_examples doesn't exceed available examples"""
        if v and "examples" in values and v > len(values["examples"]):
            raise ValueError(f"num_examples ({v}) exceeds available examples ({len(values['examples'])})")
        return v

    class Config:
        validate_assignment = True


class ChainOfThoughtPrompt(BaseModel):
    """Chain-of-thought prompting configuration"""
    problem: str = Field(..., description="Problem statement")

    # Steps
    thinking_steps: List[str] = Field(default_factory=list, description="Reasoning steps")
    step_separator: str = Field(default="\n", description="Separator between steps")

    # Format
    include_step_numbers: bool = Field(default=True, description="Number the steps")
    thinking_prefix: str = Field(default="Let's think step by step:", description="Thinking prefix")
    conclusion_prefix: str = Field(default="Therefore:", description="Conclusion prefix")

    # Options
    show_work: bool = Field(default=True, description="Show intermediate work")
    validate_logic: bool = Field(default=False, description="Validate logical flow")

    class Config:
        validate_assignment = True


class PromptOptimization(BaseModel):
    """Prompt optimization configuration"""
    base_prompt: str = Field(..., description="Original prompt")
    optimization_goal: Literal["clarity", "brevity", "accuracy", "creativity"] = Field(
        ..., description="Optimization goal"
    )

    # Optimization methods
    use_compression: bool = Field(default=False, description="Compress prompt")
    use_rephrasing: bool = Field(default=True, description="Rephrase for clarity")
    use_examples: bool = Field(default=False, description="Add examples")

    # Constraints
    max_tokens: Optional[int] = Field(default=None, ge=1, description="Maximum token limit")
    preserve_keywords: List[str] = Field(default_factory=list, description="Keywords to preserve")

    # Results
    optimized_prompt: Optional[str] = Field(default=None, description="Optimized prompt")
    optimization_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Quality score")
    token_reduction: Optional[int] = Field(default=None, description="Tokens saved")

    class Config:
        validate_assignment = True


class PromptLibrary(BaseModel):
    """Collection of prompt templates"""
    name: str = Field(..., description="Library name")
    description: Optional[str] = Field(default=None, description="Library description")

    # Templates
    templates: List[PromptTemplate] = Field(default_factory=list, description="Prompt templates")
    categories: Dict[str, List[str]] = Field(default_factory=dict, description="Template categories")

    # Metadata
    version: str = Field(default="1.0.0", description="Library version")
    author: Optional[str] = Field(default=None, description="Library author")
    license: Optional[str] = Field(default=None, description="Library license")

    # Statistics
    total_templates: int = Field(default=0, ge=0, description="Total template count")
    total_usage: int = Field(default=0, ge=0, description="Total usage count")

    # Management
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    @validator("total_templates", always=True)
    def calculate_total_templates(cls, v, values):
        """Calculate total templates"""
        if "templates" in values:
            return len(values["templates"])
        return v or 0

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get template by name"""
        for template in self.templates:
            if template.name == name:
                return template
        return None

    def get_templates_by_type(self, prompt_type: PromptType) -> List[PromptTemplate]:
        """Get templates by type"""
        return [t for t in self.templates if t.type == prompt_type]

    def get_templates_by_category(self, category: str) -> List[PromptTemplate]:
        """Get templates by category"""
        if category in self.categories:
            template_names = self.categories[category]
            return [t for t in self.templates if t.name in template_names]
        return []

    class Config:
        validate_assignment = True


class PromptEvaluation(BaseModel):
    """Evaluation metrics for prompts"""
    prompt: str = Field(..., description="Evaluated prompt")
    template_name: Optional[str] = Field(default=None, description="Template name if applicable")

    # Quality metrics
    clarity_score: float = Field(..., ge=0.0, le=1.0, description="Clarity score")
    specificity_score: float = Field(..., ge=0.0, le=1.0, description="Specificity score")
    coherence_score: float = Field(..., ge=0.0, le=1.0, description="Coherence score")

    # Performance metrics
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Task success rate")
    avg_response_quality: float = Field(..., ge=0.0, le=1.0, description="Average response quality")

    # Usage statistics
    num_uses: int = Field(default=0, ge=0, description="Number of uses")
    num_successes: int = Field(default=0, ge=0, description="Successful uses")
    num_failures: int = Field(default=0, ge=0, description="Failed uses")

    # Feedback
    user_ratings: List[float] = Field(default_factory=list, description="User ratings")
    avg_user_rating: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="Average rating")

    # Recommendations
    improvement_suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    alternative_prompts: List[str] = Field(default_factory=list, description="Alternative prompts")

    @validator("avg_user_rating", always=True)
    def calculate_avg_rating(cls, v, values):
        """Calculate average user rating"""
        if "user_ratings" in values and values["user_ratings"]:
            return sum(values["user_ratings"]) / len(values["user_ratings"])
        return v

    class Config:
        validate_assignment = True


class PromptVersion(BaseModel):
    """Version tracking for prompts"""
    version_id: str = Field(..., description="Version identifier")
    prompt_template: PromptTemplate = Field(..., description="Template at this version")

    # Version info
    version_number: str = Field(..., description="Version number (e.g., 1.2.0)")
    parent_version: Optional[str] = Field(default=None, description="Parent version ID")

    # Changes
    changes: List[str] = Field(default_factory=list, description="Changes in this version")
    change_type: Literal["major", "minor", "patch"] = Field(..., description="Type of change")

    # Performance
    performance_metrics: Optional[Dict[str, float]] = Field(default=None, description="Performance metrics")
    improvement_over_parent: Optional[float] = Field(default=None, description="Improvement percentage")

    # Metadata
    created_by: Optional[str] = Field(default=None, description="Creator")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    is_active: bool = Field(default=True, description="Whether version is active")

    class Config:
        validate_assignment = True