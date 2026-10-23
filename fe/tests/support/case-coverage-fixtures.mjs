// Synthetic browser interaction fixtures only. PostgreSQL tests prove actual authorization.
import { user as baseUser } from './ui-hierarchy-fixtures.mjs';
export const ids={author:'11111111-1111-4111-8111-111111111111',receiver:'22222222-2222-4222-8222-222222222222',outsider:'99999999-9999-4999-8999-999999999999',head:'33333333-3333-4333-8333-333333333333',student:'44444444-4444-4444-8444-444444444444',grant:'55555555-5555-4555-8555-555555555555',encounter:'66666666-6666-4666-8666-666666666666',routine:'77777777-7777-4777-8777-777777777777',handoff:'88888888-8888-4888-8888-888888888888'};
export const prefix='/api/v1/counseling/continuity-grants';
export const path=`/portal/counseling/coverage/${ids.grant}`;
export const recommendation='SYNTHETIC SELECTED RECOMMENDATION';
export function coverageFixture(options={}){
 const now=Date.now(),date=new Date(now).toISOString();
 const state={identity:options.identity??'receiver',policy:options.policy??true,empty:options.empty??false,denied:false,delay:null,writes:[],handoff:null,...options};
 state.grant={id:ids.grant,student_id:ids.student,original_counselor_id:ids.author,receiving_counselor_id:ids.receiver,requested_by_id:ids.author,requested_at:date,coverage_kind:'PLANNED_HANDOFF',reason_category:'PLANNED_ABSENCE',decision:'APPROVED',effective_status:'ACTIVE',decision_by_id:ids.head,decided_at:date,revoked_at:null,revoked_by_id:null,revocation_reason:null,version:2,policy_version:'SYNTHETIC',policy_evidence:'SYNTHETIC-ONLY',starts_at:new Date(now-60000).toISOString(),expires_at:new Date(now+3600000).toISOString(),scopes:[{id:'scope-encounter',resource_kind:'ENCOUNTER',source_id:ids.encounter,projection:'ENCOUNTER_METADATA_V1',source_revision:'synthetic'},{id:'scope-routine',resource_kind:'ROUTINE_EVALUATION',source_id:ids.routine,projection:'FINALIZED_EVALUATION_V1',source_revision:'synthetic'}],...options.grant};
 state.handoff=options.handoff?{id:ids.handoff,grant_id:ids.grant,student_id:ids.student,author_id:ids.author,receiving_counselor_id:ids.receiver,state:'SUBMITTED',submitted_at:date,version:2,created_at:date,updated_at:date,content:'SYNTHETIC CONFIDENTIAL HANDOFF',...options.handoff}:null;
 state.currentUser=()=>({...baseUser(),id:ids[state.identity]??ids.receiver,capabilities:[...baseUser().capabilities,'counseling.continuity.view','counseling.continuity.request','counseling.continuity.read_selected','counseling.handoff.manage_own','counseling.handoff.read_received',...(state.identity==='head'?['counseling.continuity.approve','counseling.continuity.revoke']:[])],designations:state.identity==='head'?['HEAD_GUIDANCE_COUNSELOR']:[]});
 state.handler=async({reply,pathname,method,request})=>{
  const fail=(code,status=403)=>reply({error:{code,message:'Synthetic operation unavailable'}},status);
  if(pathname==='/api/v1/auth/session'){if(state.logout)return fail('auth_session_invalid',401),true;return reply({user:state.currentUser(),session:{id:'synthetic-session',expires_at:'2099-01-01T00:00:00Z',is_current:true}}),true;}
  if(pathname==='/api/v1/counseling/encounters')return reply({items:[],page:1,page_size:20,has_next:false,ordering:'LATEST_START'}),true;
  if(pathname===`/api/v1/counseling/encounters/${ids.encounter}`)return reply({id:ids.encounter,student:{id:ids.student,display_name:'Synthetic Student',institutional_id:'SYNTHETIC',profile_photo_url:null},counselor:{id:ids.author,display_name:'Synthetic Author',profile_photo_url:null},service:{id:'service',name:'Counseling'},entry_mode:'WALK_IN',delivery_mode:'IN_PERSON',started_at:date,ended_at:date,created_at:date,updated_at:date,appointment:null}),true;
  if(!pathname.startsWith(prefix))return false;
  if(!state.policy)return fail('continuity_workflow_policy_unconfirmed'),true;
  if(pathname===prefix+'/workflow/configuration')return reply({server_now:new Date().toISOString(),valid_until:'2099-01-01T00:00:00Z',maximum_duration_seconds:28800,maximum_advance_seconds:172800,reason_categories:['PLANNED_ABSENCE','UNEXPECTED_ABSENCE','TEMPORARY_SUPPORT'],office_cases:state.identity==='head'?[{student_id:ids.student,original_counselor_id:ids.author}]:[],can_request:true,can_approve:state.identity==='head'}),true;
  if(pathname===prefix+'/workflow/selection')return reply({items:state.noSources?[]:state.grant.scopes.map(s=>({resource_kind:s.resource_kind,source_id:s.source_id,projection:s.projection,counselor_id:ids.author,recorded_at:date,eligible:true})),receivers:[{id:ids.receiver,name:'Synthetic Receiver'}],page:1,has_next:false}),true;
  if(pathname===prefix){
   if(method==='POST'){const data=JSON.parse(request.postData());state.writes.push(data);state.grant={...state.grant,...data,id:ids.grant,requested_by_id:state.currentUser().id,decision:'REQUESTED',effective_status:'PENDING',version:1};return reply(state.grant,201),true;}
   return reply({items:state.empty?[]:[state.grant],page:1,page_size:20,has_next:false}),true;
  }
  if(pathname===prefix+'/'+ids.grant)return reply(state.grant),true;
  const action=pathname.split('/').at(-1);
  if(['approve','decline','cancel','revoke'].includes(action)){
   state.writes.push({action});if(state.conflict)return fail('continuity_stale_version',409),true;
   if(state.identity!=='head'&&action!=='cancel'||action!=='cancel'&&[state.grant.requested_by_id,state.grant.receiving_counselor_id].includes(state.currentUser().id))return fail('continuity_self_approval'),true;
   state.grant.decision={approve:'APPROVED',decline:'DECLINED',cancel:'CANCELLED',revoke:'REVOKED'}[action];state.grant.effective_status={approve:'ACTIVE',decline:'DECLINED',cancel:'CANCELLED',revoke:'REVOKED'}[action];state.grant.version++;return reply(state.grant),true;
  }
  if(pathname.includes('/handoff/')){
   if(action==='metadata'){const item=state.handoff;const metadata=Object.fromEntries(Object.entries(item??{}).filter(([key])=>key!=='content'));return reply({handoff:item&&(item.state==='SUBMITTED'||state.identity==='author')?metadata:null}),true;}
   if(state.denied)return fail(state.deniedStatus===401?'auth_session_invalid':state.deniedStatus===403?'continuity_missing_capability':'continuity_not_found',state.deniedStatus??404),true;
   if(action==='draft'){const data=JSON.parse(request.postData());state.writes.push({action:'draft'});if(state.draftConflict){state.draftConflict=false;state.handoff.version++;state.handoff.content='OTHER SAVED SYNTHETIC DRAFT';return fail('continuity_stale_handoff_version',409),true;}state.handoff={id:ids.handoff,grant_id:ids.grant,student_id:ids.student,author_id:ids.author,receiving_counselor_id:ids.receiver,state:'DRAFT',submitted_at:null,version:(state.handoff?.version??0)+1,created_at:date,updated_at:date,content:data.content};const meta=Object.fromEntries(Object.entries(state.handoff).filter(([key])=>key!=='content'));return reply(meta),true;}
   if(action==='submit'){state.writes.push({action:'submit'});state.handoff.state='SUBMITTED';state.handoff.submitted_at=date;state.handoff.version++;const meta=Object.fromEntries(Object.entries(state.handoff).filter(([key])=>key!=='content'));return reply(meta),true;}
   if(state.handoff)return reply(state.handoff),true;return fail('continuity_not_found',404),true;
  }
  if(state.delay){await state.delay;}
  if(state.denied)return fail(state.deniedStatus===401?'auth_session_invalid':state.deniedStatus===403?'continuity_missing_capability':'continuity_not_found',state.deniedStatus??404),true;
  const common={grant_id:ids.grant,grant_version:state.grant.version,policy_version:'SYNTHETIC',disclosure_policy_version:'SYNTHETIC'};
  if(pathname.includes('/encounters/'))return reply({...common,projection:'ENCOUNTER_METADATA_V1',encounter:{id:ids.encounter,started_at:date,ended_at:date,entry_mode:'WALK_IN',delivery_mode:'IN_PERSON',counselor_id:ids.author}}),true;
  if(pathname.includes('/routine-evaluations/'))return reply({...common,projection:'FINALIZED_EVALUATION_V1',routine_interview_id:ids.routine,evaluation:state.evaluation??{academic_adjustment_rating:null,recommendations:recommendation}}),true;
  return false;
 };
 return state;
}
