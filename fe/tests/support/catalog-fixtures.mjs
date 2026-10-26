// Synthetic ORG-2 wire shapes. No live backend or institutional grants.
import { user } from "./ui-hierarchy-fixtures.mjs";
export const ids={campus:"10000000-0000-4000-8000-000000000001",college:"20000000-0000-4000-8000-000000000001",program:"30000000-0000-4000-8000-000000000001"};
const countKeys=["active_child_colleges","active_child_programs","active_student_affiliations","child_colleges","child_programs","counselor_responsibilities","draft_inventories","graduate_tracer_references","inactive_account_affiliations","issued_good_moral","open_office_threads","pending_f4","pending_good_moral","pending_operational_followups","resolved_threads","student_affiliations","submitted_inventories"];
export function catalogFixture({catalog=true,relationships=false,role="COUNSELOR",readonly=false}={}){
 const campus={id:ids.campus,code:"MAIN",name:"Main Campus",is_active:true,resource_version:1};
 const college={id:ids.college,code:"COMP",name:"College of Computing",campus,is_active:true,resource_version:1};
 const program={id:ids.program,code:"BSIS",name:"Information Systems",college,is_active:true,resource_version:1,academic_classification:"BACHELORS",year_level_policy_status:"CONFIGURED",applicable_year_levels:[1,3,5]};
 const actor={...user(role),capabilities:["organization.structure.view",...(catalog && !readonly?["organization.catalog.manage"]:[]),...(relationships?["organization.manage"]:[])]};
 const state={campuses:[campus],colleges:[college],programs:[program],actor,sessionId:"catalog-session",histories:{},writes:[],reads:[],error:null,commitThenDisconnect:false,disconnect:false,failRefresh:false,blocked:false,impactReads:0,stalePreview:false,staleOnWrite:false,verified:false,mfa:null,delay:0};
 const plural={campuses:"campus",colleges:"college",programs:"program"};
 const session=()=>({authenticated:true,user:state.actor,session:{id:state.sessionId,expires_at:"2099-10-07T00:00:00Z",is_current:true}});
 const replyError=(reply,code,status=409)=>reply({error:{code,message:"Synthetic server refusal",details:null}},status);
 function hydrate(){for(const c of state.colleges)c.campus=state.campuses.find(x=>x.id===c.campus.id);for(const p of state.programs)p.college=state.colleges.find(x=>x.id===p.college.id);}
 function history(record,collection,before,data,action){
  const fields=action==="created"?["name","is_active",...(collection==="programs"?["academic_classification","year_level_policy_status","applicable_year_levels"]:[])]:action==="updated"?["name"]:action==="policy_changed"?["academic_classification","year_level_policy_status","applicable_year_levels"]:["is_active"];
  const pick=r=>Object.fromEntries(fields.map(k=>[k,r[k]]));
  const item={id:`event-${state.writes.length}`,action:`organization.${plural[collection]}.${action}`,actor_id:state.actor.id,basis:data.basis,code:record.code,parent_id:record.college?.id??record.campus?.id??null,resource_version_before:before?.resource_version??null,resource_version_after:record.resource_version,before:before?pick(before):{},after:pick(record),changed_fields:fields,occurred_at:new Date().toISOString()};
  (state.histories[record.id]??=[]).unshift(item);
 }
 const handler=async({route,reply,request,pathname,method,url})=>{
  if(pathname==="/api/v1/auth/session"){await reply(session());return true;}
  if(pathname==="/api/v1/auth/mfa/totp/verify" && method==="POST"){state.verified=true;await reply({verified:true});return true;}
  if(pathname==="/api/v1/auth/mfa"){await reply({enabled:true,verified_recently:state.verified});return true;}
  if(!pathname.startsWith("/api/v1/organization/"))return false;
  const parts=pathname.split("/").slice(4);const [collection,id,action]=parts;
  if(!["campuses","colleges","programs"].includes(collection))return false;
  hydrate();const records=state[collection];const record=records.find(r=>r.id===id);
  if(method==="GET"){
    state.reads.push({collection,id,action});
    if(state.readError && (state.readError===action || state.readError===collection || state.readError==="all")){await replyError(reply,"synthetic_unavailable",503);return true;}
    if(!id){if(state.failRefresh && state.writes.length){await replyError(reply,"synthetic_unavailable",503);return true;}await reply({items:records});return true;}
    if(!record){await replyError(reply,"catalog_not_found",404);return true;}
    if(action==="impact"){
      state.impactReads++;
      const blocked=state.blocked||(state.stalePreview&&state.impactReads>=2);
      const blockers=blocked?[{code:collection==="campuses"?"active_child_colleges":collection==="colleges"?"active_student_affiliations":"open_office_threads",count:2}]:[];
      const counts=Object.fromEntries(countKeys.map(k=>[k,0]));counts.draft_inventories=2;counts.submitted_inventories=9;
      for(const b of blockers)counts[b.code]=b.count;
      await reply({target_id:id,resource_version:record.resource_version,observed_at:new Date().toISOString(),can_deactivate:!blocked,blockers,warnings:[{code:"draft_inventories",count:2}],counts,preserved_categories:["submitted_inventory_facts","issued_certificate_snapshots","graduate_tracer_references","resolved_guidance_threads","inactive_affiliations"]});return true;
    }
    if(action==="history"){
      const page=Number(url.searchParams.get("page")??1);const pageSize=Number(url.searchParams.get("page_size")??10);const all=state.histories[id]??[];
      await reply({items:all.slice((page-1)*pageSize,page*pageSize),page,page_size:pageSize,has_next:all.length>page*pageSize});return true;
    }
    if(state.oldRecord?.id===id){const old=state.oldRecord;state.oldRecord=null;await reply(old);return true;}
    await reply(record);return true;
  }
  const data=JSON.parse(request.postData()??"{}");state.writes.push({collection,id,action,method,data});
  if(state.delay)await new Promise(r=>setTimeout(r,state.delay));
  if(state.mfa&&!state.verified){await replyError(reply,state.mfa,403);return true;}
  if(state.error){await replyError(reply,state.error,state.error==="permission_denied"?403:409);return true;}
  if(state.disconnect){await route.abort("failed");return true;}
  if(state.staleOnWrite&&record){state.staleOnWrite=false;record.name="Updated by another administrator";record.resource_version++;await replyError(reply,"catalog_stale_version");return true;}
  const snapshot=record?structuredClone(record):null;
  let result;
  if(method==="POST"){
    if(records.some(r=>r.code===data.code&&(collection==="campuses"||(r.campus?.id??r.college?.id)===(data.campus_id??data.college_id)))){await replyError(reply,"catalog_duplicate_code");return true;}
    const common={id:`${collection}-new-${state.writes.length}`,code:data.code,name:data.name,is_active:data.is_active,resource_version:1};
    result=collection==="campuses"?common:collection==="colleges"?{...common,campus:state.campuses.find(c=>c.id===data.campus_id)}:{...common,college:state.colleges.find(c=>c.id===data.college_id),academic_classification:data.academic_classification,year_level_policy_status:data.year_level_policy_status,applicable_year_levels:data.applicable_year_levels};
    records.push(result);history(result,collection,null,data,"created");
  }else{
    if(!record){await replyError(reply,"catalog_not_found",404);return true;}
    if(record.resource_version!==data.expected_resource_version){await replyError(reply,"catalog_stale_version");return true;}
    const before=structuredClone(record);
    if(action==="name")record.name=data.name;
    if(action==="active")record.is_active=data.is_active;
    if(action==="policy")Object.assign(record,{academic_classification:data.academic_classification,year_level_policy_status:data.year_level_policy_status,applicable_year_levels:data.applicable_year_levels});
    record.resource_version++;
    history(record,collection,before,data,action==="name"?"updated":action==="policy"?"policy_changed":record.is_active?"enabled":"disabled");result=record;
  }
  if(state.commitThenDisconnect){state.commitThenDisconnect=false;if(state.returnOldOnce)state.oldRecord=snapshot;await route.abort("failed");return true;}
  await reply(result);return true;
 };
 return {state,handler,campus,college,program,session};
}
