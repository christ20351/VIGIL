function renderDashboardView() {
  if (typeof renderComputers === "function") {
    renderComputers();
  } else {
    console.warn("renderComputers() not defined yet");
  }
}
