import assert from "node:assert/strict";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { canEnterOrganization, canManageOrganization, canManageOrganizationCatalog } from "../src/features/institution-configuration/institution-access.ts";
import { portalWorkspaceGroups } from "../src/features/portal/components/portal-workspaces.ts";
import { portalCommandDestinations } from "../src/features/portal/components/portal-command-destinations.ts";
import { academicProgramLabel, levelsLabel, initialDraft, makeCommand, draftError, filterHierarchy } from "../src/features/organization/structure/catalog/catalog-model.ts";
import { historyConfirmsCommand } from "../src/features/organization/structure/catalog/catalog-query.ts";
import { catalogErrorMessage, uncertainCatalogOutcome } from "../src/features/organization/structure/catalog/catalog-errors.ts";
import { CatalogImpact } from "../src/features/organization/structure/catalog/catalog-impact.tsx";
import { CompassApiError } from "../src/lib/api/errors.ts";
import { assertBrowserSuiteInCI } from "./support/browser-registration.mjs";

const campus = { id: "campus-a", code: "MAIN", name: "Main Campus", resource_version: 3, is_active: true };
const college = { ...campus, id: "college-a", code: "CC", name: "Computing", campus };
const program = { ...campus, id: "program-a", code: "P1", name: "Computing Program", college, academic_classification: "BACHELORS", year_level_policy_status: "CONFIGURED", applicable_year_levels: [1,3,5] };
const target = { kind: "program", record: program };
const account = (role, capabilities) => ({ id: "actor", role, capabilities, designations: [], first_name: "Test", last_name: "User", email: "test@example.test", student_lifecycle_status: null });
for (const [name, role, capabilities, enter, edit, relationships] of [
  ["Catalog only", "COUNSELOR", ["organization.structure.view", "organization.catalog.manage"], true,true,false],
  ["Relationships only", "COUNSELOR", ["organization.structure.view", "organization.manage"], true,false,true],
  ["Both", "IT_ADMIN", ["organization.structure.view", "organization.manage", "organization.catalog.manage"], true,true,true],
  ["Staff reference viewer", "GUIDANCE_SERVICES_STAFF", ["organization.structure.view"], true,false,false],
  ["Student selector reader", "STUDENT", ["organization.structure.view"], false,false,false],
  ["Unsupported Catalog grant", "INSTITUTIONAL_OFFICER", ["organization.structure.view", "organization.catalog.manage"], false,false,false],
  ["Missing structure dependency", "IT_ADMIN", ["organization.catalog.manage"], false,false,false],
  ["Revoked Catalog capability", "COUNSELOR", ["organization.structure.view"], true,false,false],
]) test(`Organization access: ${name}`, () => {
  const user = account(role, capabilities);
  assert.equal(canEnterOrganization(user),enter); assert.equal(canManageOrganizationCatalog(user),edit); assert.equal(canManageOrganization(user),relationships);
  const dock = portalWorkspaceGroups(user).flatMap((group) => group.links).map((link) => link.href);
  assert.equal(dock.includes("/portal/organization"),enter);
  const commands = portalCommandDestinations(user).map((item) => item.href);
  assert.equal(commands.includes("/portal/organization/responsibilities"),enter && relationships);
  assert.equal(commands.includes("/portal/organization/student-affiliations"),enter && relationships);
});
for (const [levels,status,result] of [[[1,3,5],"CONFIGURED","1st, 3rd and 5th Year"],[[1,2,3,4],"CONFIGURED","1st–4th Year"],[[1,3],"CONFIGURED","1st and 3rd Year"],[[10],"CONFIGURED","10th Year"],[null,"PENDING_POLICY","Year levels not set"]]) test(`Actual Year Levels: ${JSON.stringify(levels)}`,()=>assert.equal(levelsLabel(levels,status),result));
test("Unknown classification is explicit, never inferred from a Program name",()=>assert.equal(academicProgramLabel({...program, name:"Bachelor of Something",academic_classification:null,year_level_policy_status:"PENDING_POLICY",applicable_year_levels:null}),"Classification not set · Year levels not set"));
for (const [kind,parent,operation] of [["campus",null,"createCampus"],["college",{kind:"campus",record:campus},"createCollege"],["program",{kind:"college",record:college},"createProgram"]]) test(`Strict ${kind} creation preserves fixed ancestry and explicit inactive state`,()=>{
 const intent={mode:"create",kind,...(parent?{parent}:{})};const draft={...initialDraft(intent),name:"New definition",code:" new_code ",active:"inactive",basis:"Approved memo"};
 assert.equal(draftError(intent,draft),null);const command=makeCommand(intent,draft);assert.equal(command.operation,operation);assert.equal(command.data.is_active,false);assert.equal(command.data.code,"NEW_CODE");
 assert.equal("expected_resource_version" in command.data,false);assert.equal("mfa_verified" in command.data,false);
 if(kind==="college")assert.equal(command.data.campus_id,campus.id);
 if(kind==="program"){assert.equal(command.data.college_id,college.id);assert.equal(command.data.academic_classification,null);assert.equal(command.data.applicable_year_levels,null);}
});
test("Program starts without a guessed classification, levels or active state",()=>{
 const d=initialDraft({mode:"create",kind:"program",parent:{kind:"college",record:college}});assert.equal(d.classification,null);assert.deepEqual(d.levels,[]);assert.equal(d.active,"");
});
for(const [label,change] of [["missing status",{}],["incomplete active policy",{active:"active"}],["empty configured levels",{active:"inactive",classification:"MASTERS",policyStatus:"CONFIGURED"}],["unknown configured classification",{active:"inactive",policyStatus:"CONFIGURED",levels:[1]}],["invalid level",{active:"inactive",classification:"DOCTORAL",policyStatus:"CONFIGURED",levels:[11]}],["blank basis",{active:"inactive",basis:" "}],["invalid code",{active:"inactive",code:"wrong code"}]]) test(`Creation rejects ${label}`,()=>{
 const intent={mode:"create",kind:"program",parent:{kind:"college",record:college}};const d={...initialDraft(intent),name:"New",code:"NEW",basis:"Memo",...change};assert.ok(draftError(intent,d));
});
test("Active Program explicitly configures a noncontiguous set without filling gaps",()=>{
 const intent={mode:"create",kind:"program",parent:{kind:"college",record:college}};const d={...initialDraft(intent),name:"New",code:"NEW",basis:"Memo",active:"active",classification:"MASTERS",policyStatus:"CONFIGURED",levels:[5,1,3,3]};assert.equal(draftError(intent,d),null);assert.deepEqual(makeCommand(intent,d).data.applicable_year_levels,[1,3,5]);
});
test("Rename contains only name, basis and reviewed resource version",()=>{
 const intent={mode:"rename",target};const d={...initialDraft(intent),name:"New name",basis:"Memo",code:"ATTACK"};const command=makeCommand(intent,d,target);assert.deepEqual(command.data,{name:"New name",basis:"Memo",expected_resource_version:3});
});
test("Normalized rename no-op has honest feedback",()=>{const i={mode:"rename",target};assert.match(draftError(i,{...initialDraft(i),name:` ${program.name} `,basis:"Memo"},target),/has not changed/);});
test("Policy no-op is refused, pending sends null rather than an empty set",()=>{
 const i={mode:"policy",target};const d={...initialDraft(i),basis:"Memo"};assert.match(draftError(i,d,target),/have not changed/);const data=makeCommand(i,{...d,policyStatus:"PENDING_POLICY"},target).data;assert.equal(data.applicable_year_levels,null);assert.equal(data.expected_resource_version,3);
});
test("Status actions carry explicit desired state and current version without preview authority",()=>{
 const i={mode:"status",target};const c=makeCommand(i,{...initialDraft(i),basis:"Memo"},target);assert.deepEqual(c.data,{basis:"Memo",expected_resource_version:3,is_active:false});assert.equal("can_deactivate" in c.data,false);
 assert.match(draftError(i,{...initialDraft(i),basis:"Memo"},{...target,record:{...program,is_active:false}}),/already changed/);
});
test("Search retains actual ancestor context for a noncontiguous Program match",()=>{
 const out=filterHierarchy([campus],[college],[program],{search:"P1",status:"",campus:"",college:""});assert.equal(out[0].contextOnly,true);assert.equal(out[0].colleges[0].contextOnly,true);assert.equal(out[0].colleges[0].programs[0].id,program.id);
});
test("Inactive descendants keep parent context; unrelated parents do not become blank rows",()=>{
 const out=filterHierarchy([campus,{...campus,id:"other"}],[college],[{...program,is_active:false}],{search:"",status:"inactive",campus:"",college:""});assert.equal(out.length,1);assert.equal(out[0].contextOnly,true);
});
const item={id:"event",action:"organization.program.updated",actor_id:"actor",basis:"Memo",code:program.code,parent_id:college.id,resource_version_before:3,resource_version_after:4,before:{name:program.name},after:{name:"New name"},occurred_at:"2026-10-26T00:00:00Z",changed_fields:["name"]};
const command={operation:"rename",target,data:{name:"New name",basis:"Memo",expected_resource_version:3}};
test("Uncertain rename is confirmed only by attributable versioned target history",()=>{
 assert.equal(historyConfirmsCommand(command,item,"actor"),true);
 for(const patch of [{actor_id:"other"},{basis:"Other"},{resource_version_before:2},{resource_version_after:5},{after:{name:"Other"}},{action:"organization.program.created"}])assert.equal(historyConfirmsCommand(command,{...item,...patch},"actor"),false);
});
test("Creation reconciliation requires version-one creation, matching parent and exact policy",()=>{
 const c={operation:"createProgram",data:{name:"New name",basis:"Memo",code:program.code,college_id:college.id,is_active:false,academic_classification:null,year_level_policy_status:"PENDING_POLICY",applicable_year_levels:null}};
 const h={...item,action:"organization.program.created",resource_version_before:null,resource_version_after:1,after:{name:"New name",is_active:false,academic_classification:null,year_level_policy_status:"PENDING_POLICY",applicable_year_levels:null}};assert.equal(historyConfirmsCommand(c,h,"actor"),true);assert.equal(historyConfirmsCommand(c,{...h,parent_id:"other"},"actor"),false);
});
for(const code of ["permission_denied","invalid_session","mfa_setup_required","recent_mfa_required","catalog_not_found","catalog_duplicate_code","catalog_stale_version","catalog_inactive_parent","catalog_deactivation_blocked","catalog_policy_approval_required","catalog_pending_f4_policy_decision_required","catalog_not_initialized","catalog_busy","invalid_catalog_request"])test(`Safe actionable error: ${code}`,()=>{
 const err=new CompassApiError({status:409,body:{error:{code,message:"SECRET SQL OR PRIVATE DATA"}},headers:{},method:"PUT",url:"/api/v1/organization/programs/id/policy"});assert.doesNotMatch(catalogErrorMessage(err),/SECRET|SQL/);assert.equal(uncertainCatalogOutcome(err),false);
});
test("Network and server errors require read-only reconciliation",()=>{assert.equal(uncertainCatalogOutcome(new TypeError("Failed to fetch")),true);assert.equal(uncertainCatalogOutcome(new CompassApiError({status:503,body:{},headers:{},method:"POST",url:"/api/v1/organization/campuses"})),true);});
test("Impact distinguishes blockers/warnings, safe counts and authorized remediation only",()=>{
 const impact={target_id:program.id,resource_version:3,observed_at:"2026-10-26T00:00:00Z",can_deactivate:false,blockers:[{code:"active_student_affiliations",count:7}],warnings:[{code:"draft_inventories",count:2}],counts:{draft_inventories:2},preserved_categories:["submitted_inventory_facts","issued_certificate_snapshots"]};
 const html=renderToStaticMarkup(createElement(CatalogImpact,{impact,canManageRelationships:false}));assert.match(html,/Deactivation blocked/);assert.match(html,/Count: 7/);assert.match(html,/Warnings/);assert.match(html,/Submitted Inventory facts/);assert.doesNotMatch(html,/href=/);const authorized=renderToStaticMarkup(createElement(CatalogImpact,{impact,canManageRelationships:true}));assert.match(authorized,/student-affiliations/);
});
test("Catalog browser suite is registered once per engine in CI discovery",()=>assertBrowserSuiteInCI("organization-catalog.browser.mjs"));
test("Contract declares all sixteen integrated operations and no Catalog API changes",()=>{
 const spec=JSON.parse(readFileSync(new URL("../../contracts/openapi.json",import.meta.url),"utf8"));const operations=Object.values(spec.paths).flatMap((path)=>Object.values(path).map((op)=>op.operationId));
 for(const kind of ["Campus","College","Program"])for(const action of ["Create","Rename","Set","GetImpact","GetHistory"]){const id=action==="Set"?`organizationSet${kind}Active`:action==="GetImpact"?`organizationGet${kind}Impact`:action==="GetHistory"?`organizationGet${kind}History`:`organization${action}${kind}`;assert.ok(operations.includes(id),id);}assert.ok(operations.includes("organizationUpdateProgramPolicy"));
});

for (const [operation,extra,after,action] of [
 ["status",{is_active:false},{is_active:false},"organization.program.disabled"],
 ["status",{is_active:true},{is_active:true},"organization.program.enabled"],
 ["policy",{academic_classification:"MASTERS",year_level_policy_status:"CONFIGURED",applicable_year_levels:[1,3,5]},{academic_classification:"MASTERS",year_level_policy_status:"CONFIGURED",applicable_year_levels:[1,3,5]},"organization.program.policy_changed"],
 ["policy",{academic_classification:null,year_level_policy_status:"PENDING_POLICY",applicable_year_levels:null},{academic_classification:null,year_level_policy_status:"PENDING_POLICY",applicable_year_levels:null},"organization.program.policy_changed"],
]) test(`Uncertain ${action} requires the exact proposed state and version evidence`,()=>{
 const c={operation,target,data:{basis:"Memo",expected_resource_version:3,...extra}};
 const h={...item,action,after};assert.equal(historyConfirmsCommand(c,h,"actor"),true);
 assert.equal(historyConfirmsCommand(c,{...h,resource_version_after:3},"actor"),false);
 assert.equal(historyConfirmsCommand(c,{...h,after:{}},"actor"),false);
});

test("A timeout response is also an uncertain mutation outcome",()=>{assert.equal(uncertainCatalogOutcome(new CompassApiError({status:408,body:{},headers:{},method:"PUT",url:"/api/v1/organization/campuses/id/name"})),true);});
