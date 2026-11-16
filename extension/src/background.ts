chrome.runtime.onInstalled.addListener(() => {
  void Promise.all([
    chrome.storage.sync.remove([
      "erph_profiles",
      "erph_active_profile",
      "erph_active_profile_id",
      "erph_field_mappings",
    ]),
    chrome.storage.local.remove([
      "erph_fill_log",
      "erph_imported_plans",
      "erph_active_plan",
    ]),
  ]).catch(error => {
    console.error("[eRPH-PM] Could not remove legacy extension data", error);
  });
});
