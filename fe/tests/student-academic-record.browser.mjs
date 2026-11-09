import assert from "node:assert/strict";
import { createBrowserHarness } from "./support/browser-harness.mjs";
import { catalogFixture, ids } from "./support/catalog-fixtures.mjs";

const h=await createBrowserHarness("student-academic-record");
const directoryPath="/portal/organization/student-academics";
const detailPath=`${directoryPath}/${ids.student}`;
function academicFixture({years=true}={}){
 const f=catalogFixture({catalog:false,relationships:true});
 if(years)f.state.actor.capabilities.push("academic_years.view");
 f.state.placements=[f.placement];f.state.records[ids.student]=f.studentRecord;
 return f;
}

{
 const f=academicFixture();
 await h.check("01 Directory Student link opens the aggregate record",directoryPath,{handler:f.handler},async(page)=>{
  await h.shown(page.getByRole("heading",{name:"Student Academic Records",exact:true}));
  const link=page.getByRole("link",{name:"Maria Santos",exact:true});
  assert.equal(await link.getAttribute("href"),detailPath);
  await link.click();
  await h.shown(page.getByRole("heading",{name:"Maria Santos",exact:true}));
  await h.shown(page.getByText("Current placement",{exact:true}));
  await h.shown(page.getByText("College of Computing",{exact:true}));
  await h.shown(page.getByText("Main Campus",{exact:true}));
  await h.shown(page.getByText("No academic periods recorded.",{exact:true}));
  await h.shown(page.getByText("No graduation recorded.",{exact:true}));
  assert.ok(f.state.recordReads>=1);
 });
}

{
 const f=academicFixture();
 await h.check("02 Period recording saves the exact classification and refetches the aggregate",detailPath,{handler:f.handler},async(page)=>{
  await h.shown(page.getByRole("heading",{name:"Maria Santos",exact:true}));
  await page.getByRole("button",{name:"Record period",exact:true}).click();
  const dialog=page.getByRole("dialog");
  await h.shown(dialog.getByRole("heading",{name:"Record academic period",exact:true}));
  await dialog.getByLabel("Academic year",{exact:true}).selectOption(ids.academicYear);
  await dialog.getByLabel("Term",{exact:true}).selectOption("FIRST_SEMESTER");
  await dialog.getByLabel("College",{exact:true}).selectOption(ids.college);
  await dialog.getByLabel("Year level (optional)",{exact:true}).fill("2");
  await dialog.getByLabel("Enrollment status",{exact:true}).selectOption("ENROLLED");
  await dialog.getByRole("button",{name:"Save period",exact:true}).click();
  await h.shown(page.getByText("Academic period recorded.",{exact:true}));
  await h.hidden(dialog);
  assert.deepEqual(f.state.writes[0].data,{academic_year_id:ids.academicYear,term:"FIRST_SEMESTER",college_id:ids.college,year_level:2,enrollment_status:"ENROLLED"});
  await h.shown(page.getByRole("rowheader",{name:"2026-2027",exact:true}));
  await h.shown(page.getByRole("cell",{name:"First Semester",exact:true}));
  await h.shown(page.getByRole("cell",{name:"Enrolled",exact:true}));
  await h.shown(page.getByText("1 recorded",{exact:true}));
  assert.ok(f.state.recordReads>=2);
 });
}

{
 const f=academicFixture();
 await h.check("03 Graduation states consequences, completes in place, and clears placement and lifecycle after refetch",detailPath,{handler:f.handler},async(page)=>{
  await h.shown(page.getByRole("heading",{name:"Maria Santos",exact:true}));
  await page.getByRole("button",{name:"Record graduation",exact:true}).click();
  const form=page.getByRole("dialog");
  await h.shown(form.getByRole("heading",{name:"Record graduation",exact:true}));
  await form.getByLabel("Graduation date",{exact:true}).fill("2027-06-30");
  await form.getByLabel("College",{exact:true}).selectOption(ids.college);
  await form.getByLabel("Verification source",{exact:true}).fill("Registrar confirmation 2027");
  await form.getByRole("button",{name:"Review graduation",exact:true}).click();
  const confirmation=page.getByRole("alertdialog");
  await h.shown(confirmation.getByRole("heading",{name:"Record graduation?",exact:true}));
  await h.shown(confirmation.getByText(/Recording graduation clears the current placement and sets the Student lifecycle to Graduated\. Exit Interview and Good Moral are not checked or changed\./));
  await h.shown(confirmation.getByText("Will be cleared",{exact:true}));
  assert.equal(f.state.writes.length,0,"confirmation alone never writes");
  await confirmation.getByRole("button",{name:"Record graduation",exact:true}).click();
  await h.shown(confirmation.getByRole("heading",{name:"Graduation recorded.",exact:true}));
  await h.shown(confirmation.getByText(/Maria Santos is recorded as graduated from College of Computing on Jun 30, 2027\./));
  await h.shown(confirmation.getByText("The current placement is cleared and the Student lifecycle is Graduated. Exit Interview and Good Moral were not checked or changed.",{exact:true}));
  assert.deepEqual(f.state.writes[0].data,{graduated_college_id:ids.college,graduation_date:"2027-06-30",verification_source:"Registrar confirmation 2027"});
  await confirmation.getByRole("button",{name:"Done",exact:true}).click();
  await h.hidden(confirmation);
  await h.shown(page.getByText("No current College placement.",{exact:true}));
  await h.shown(page.getByText("Graduated",{exact:true}));
  const graduationPanel=page.locator("section[aria-labelledby='graduation-heading']");
  await h.shown(graduationPanel.getByText("Registrar confirmation 2027",{exact:true}));
  await h.shown(graduationPanel.getByText("Example User",{exact:true}));
  assert.equal(f.studentRecord.placement,null);
  assert.equal(f.studentRecord.lifecycle_status,"GRADUATED");
  assert.ok(f.state.recordReads>=2);
 });
}

{
 const f=academicFixture({years:false});
 f.studentRecord.periods=[{id:"period-existing",academic_year:f.state.academicYears[0],term:"SECOND_SEMESTER",college:f.college,year_level:3,enrollment_status:"ENROLLED",created_at:"2026-07-01T00:00:00Z",updated_at:"2026-07-01T00:00:00Z"}];
 await h.check("04 Missing Academic Years authority disables period recording but keeps facts visible",detailPath,{handler:f.handler},async(page)=>{
  await h.shown(page.getByText("Academic Years are unavailable to this account, so academic periods cannot be recorded.",{exact:true}));
  assert.equal(await page.getByRole("button",{name:"Record period",exact:true}).isDisabled(),true);
  await h.shown(page.getByRole("rowheader",{name:"2026-2027",exact:true}));
  await h.shown(page.getByRole("cell",{name:"Second Semester",exact:true}));
  await h.shown(page.getByRole("cell",{name:"3",exact:true}));
 });
}

{
 const f=academicFixture();
 f.state.actor.capabilities=f.state.actor.capabilities.filter((capability)=>capability!=="student_academics.manage");
 f.studentRecord.periods=[{id:"period-existing",academic_year:f.state.academicYears[0],term:"SECOND_SEMESTER",college:f.college,year_level:3,enrollment_status:"ENROLLED",created_at:"2026-07-01T00:00:00Z",updated_at:"2026-07-01T00:00:00Z"}];
 await h.check("05 View-only access shows the record without write controls",detailPath,{handler:f.handler},async(page)=>{
  await h.shown(page.getByRole("heading",{name:"Maria Santos",exact:true}));
  await h.shown(page.locator("section[aria-labelledby='current-placement-heading']").getByText("College of Computing",{exact:true}));
  assert.equal(await page.getByRole("button",{name:"Record period",exact:true}).count(),0);
  assert.equal(await page.getByRole("button",{name:"Update",exact:true}).count(),0);
  assert.equal(await page.getByRole("button",{name:"Record graduation",exact:true}).count(),0);
  assert.equal(await page.getByRole("columnheader",{name:"Action",exact:true}).count(),0);
  assert.equal(f.state.writes.length,0);
 });
}

await h.finish();
