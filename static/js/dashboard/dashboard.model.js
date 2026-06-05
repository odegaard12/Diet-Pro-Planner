/**
 * Dashboard view-model helpers.
 * v0.0.15 will move dashboard calculations here gradually.
 */

export function mealsForDay(state, dateValue) {
  return (state?.meals || []).filter((meal) => meal.date === dateValue);
}

export function workoutsForDay(state, dateValue) {
  return (state?.workouts || []).filter((workout) => workout.date === dateValue);
}

export function mealTotals(meals) {
  return (meals || []).reduce((acc, meal) => {
    const totals = meal.totals || {};
    acc.kcal += Number(totals.kcal || 0);
    acc.protein += Number(totals.protein || 0);
    acc.oil += (meal.items || [])
      .filter((item) => /aceite/i.test(item.food_name || item.name || ''))
      .reduce((sum, item) => sum + Number(item.grams || 0), 0);
    return acc;
  }, { kcal: 0, protein: 0, oil: 0 });
}

export function workoutTotals(workouts) {
  return (workouts || []).reduce((sum, workout) => sum + Number(workout.kcal || 0), 0);
}
