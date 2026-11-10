// Select through the same month/year controls and day buttons as a booking user.
export async function chooseAppointmentDate(scope, value, label = "Appointment date") {
  const calendar = scope.getByRole("group", { name: label, exact: true });
  await calendar.getByLabel("Year", { exact: true }).fill(value.slice(0, 4));
  await calendar.getByRole("button", { name: "Go", exact: true }).click();
  await calendar.getByLabel("Month", { exact: true }).selectOption(String(Number(value.slice(5, 7)) - 1));
  await calendar.locator(`[data-day="${value}"] button`).click();
}
