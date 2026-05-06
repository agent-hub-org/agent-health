from pydantic import BaseModel, Field


class HealthProfileRequest(BaseModel):
    goals: str = Field(
        default="",
        description="Primary fitness goal: weight loss, muscle gain, endurance, general fitness, etc.",
    )
    fitness_level: str = Field(
        default="beginner",
        description="Self-assessed fitness level: beginner, intermediate, or advanced.",
    )
    available_equipment: list[str] = Field(
        default_factory=list,
        description="Equipment available (e.g. ['dumbbells', 'resistance bands', 'gym access']).",
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list,
        description="Dietary restrictions or preferences (e.g. ['vegetarian', 'gluten-free']).",
    )
    injuries_or_limitations: str = Field(
        default="",
        description="Any injuries, chronic pain, or physical limitations to account for.",
    )
    age: int | None = Field(default=None, description="User's age in years.")
    weight_kg: float | None = Field(default=None, description="Current weight in kilograms.")
    height_cm: float | None = Field(default=None, description="Height in centimetres.")
    sessions_per_week: int | None = Field(default=None, description="Preferred workout sessions per week.")
    minutes_per_session: int | None = Field(default=None, description="Minutes available per workout session.")


class HealthProfileResponse(BaseModel):
    user_id: str
    goals: str
    fitness_level: str
    available_equipment: list[str]
    dietary_restrictions: list[str]
    injuries_or_limitations: str
    age: int | None
    weight_kg: float | None
    height_cm: float | None
    sessions_per_week: int | None
    minutes_per_session: int | None


class ProgressLogRequest(BaseModel):
    metric_type: str
    value: float
    unit: str
    notes: str = ""
    date: str | None = None


class NutritionLogRequest(BaseModel):
    meal_description: str
    calories_kcal: float
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    meal_type: str = "meal"
    date: str | None = None
