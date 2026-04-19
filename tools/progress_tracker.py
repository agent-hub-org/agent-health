"""Tools for tracking health progress: workouts, measurements, and nutrition."""
import logging
from datetime import datetime, timezone

from langchain_core.tools import tool

logger = logging.getLogger("agent_health.tools.progress_tracker")


@tool
async def log_progress(
    user_id: str,
    metric_type: str,
    value: float,
    unit: str,
    notes: str = "",
    date: str = "",
) -> str:
    """Log a health or fitness measurement for the user.

    Args:
        user_id: The user's ID (from context — always pass the user_id from [CONTEXT]).
        metric_type: Type of measurement. Examples: "weight_kg", "body_fat_pct",
                     "bench_press_kg", "squat_kg", "deadlift_kg", "run_km",
                     "calories_kcal", "protein_g", "carbs_g", "fat_g",
                     "waist_cm", "chest_cm", "resting_hr_bpm", "sleep_hours".
        value: Numeric value of the measurement.
        unit: Unit of the measurement (e.g. "kg", "cm", "%", "kcal", "km").
        notes: Optional context or notes (e.g. "felt strong today", "after meal").
        date: ISO date string (YYYY-MM-DD). Defaults to today if empty.
    """
    from database.mongo import MongoDB

    if not user_id:
        return "Cannot log progress: user_id is required."

    log_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await MongoDB.log_progress(
        user_id=user_id,
        metric_type=metric_type,
        value=value,
        unit=unit,
        notes=notes,
        date=log_date,
    )

    logger.info("Logged progress for user='%s': %s=%.2f %s on %s", user_id, metric_type, value, unit, log_date)
    return f"Logged: {metric_type} = {value} {unit} on {log_date}."


@tool
async def get_progress_summary(
    user_id: str,
    metric_type: str,
    days: int = 30,
) -> str:
    """Retrieve recent progress data for a specific metric.

    Args:
        user_id: The user's ID (from context).
        metric_type: The metric to retrieve (e.g. "weight_kg", "bench_press_kg").
        days: Number of past days to include (default: 30).
    """
    from database.mongo import MongoDB

    if not user_id:
        return "Cannot fetch progress: user_id is required."

    entries = await MongoDB.get_progress(user_id=user_id, metric_type=metric_type, days=days)
    if not entries:
        return f"No {metric_type} data found in the last {days} days."

    lines = [f"**{metric_type} — last {days} days ({len(entries)} entries)**"]
    for e in entries:
        note = f" ({e['notes']})" if e.get("notes") else ""
        lines.append(f"- {e['date']}: {e['value']} {e['unit']}{note}")

    if len(entries) >= 2:
        first_val = entries[0]["value"]
        last_val = entries[-1]["value"]
        change = last_val - first_val
        sign = "+" if change >= 0 else ""
        lines.append(f"\n**Trend:** {sign}{change:.2f} {entries[0]['unit']} over this period")

    return "\n".join(lines)


@tool
async def log_nutrition(
    user_id: str,
    meal_description: str,
    calories_kcal: float,
    protein_g: float = 0.0,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
    meal_type: str = "meal",
    date: str = "",
) -> str:
    """Log a meal or nutrition entry for the user.

    Args:
        user_id: The user's ID (from context).
        meal_description: Brief description of what was eaten (e.g. "chicken rice bowl").
        calories_kcal: Estimated calories.
        protein_g: Protein in grams.
        carbs_g: Carbohydrates in grams.
        fat_g: Fat in grams.
        meal_type: "breakfast", "lunch", "dinner", "snack", or "meal".
        date: ISO date string (YYYY-MM-DD). Defaults to today.
    """
    from database.mongo import MongoDB

    if not user_id:
        return "Cannot log nutrition: user_id is required."

    log_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await MongoDB.log_nutrition(
        user_id=user_id,
        meal_description=meal_description,
        calories_kcal=calories_kcal,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        meal_type=meal_type,
        date=log_date,
    )

    daily_total = await MongoDB.get_daily_nutrition_total(user_id=user_id, date=log_date)

    summary = (
        f"Logged: {meal_description} — {calories_kcal:.0f} kcal "
        f"(P: {protein_g:.0f}g / C: {carbs_g:.0f}g / F: {fat_g:.0f}g)\n"
        f"**Today's total so far:** {daily_total['calories_kcal']:.0f} kcal | "
        f"Protein: {daily_total['protein_g']:.0f}g | "
        f"Carbs: {daily_total['carbs_g']:.0f}g | "
        f"Fat: {daily_total['fat_g']:.0f}g"
    )
    logger.info("Logged nutrition for user='%s' on %s: %.0f kcal", user_id, log_date, calories_kcal)
    return summary
