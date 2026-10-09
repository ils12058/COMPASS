import { user } from "./ui-hierarchy-fixtures.mjs";
export const student={id:'student',display_name:'Maria Santos',institutional_id:'TEST-01'};
export const year={id:'year',label:'2026–2027',is_current:true};
export const empty={items:[],page:1,page_size:20,has_next:false};
export const longEmail='a'.repeat(64)+'@'+'b'.repeat(63)+'.'+'c'.repeat(40)+'.edu';
export const auth={'/api/v1/auth/session':{user:{...user(),capabilities:[...user().capabilities,'accounts.manage','resources.manage','inventory.view','exit_interviews.view','exit_interviews.manage_opportunities','availability.manage','announcements.manage','referrals.view']},session:{id:'s',expires_at:'2099-01-01T00:00:00Z',is_current:true}}};
export const account={...user('STUDENT'),full_name:'Maria Santos',email:longEmail,first_name:'Maria',last_name:'Santos',is_active:true,email_verified:true};
export const worlds={...auth,
'/api/v1/accounts':({reply,url}) => reply({...empty, items:[account], page:Number(url.searchParams.get('page')??1), has_next:true, ordering:url.searchParams.get('ordering')??'NAME_ASC'}),
'/api/v1/inventory/students':{...empty,filter_options:{form_revisions:[]},items:[{student,academic_year:year,status:'SUBMITTED',inventory_id:'inv',program:null,year_level:4,correction_pending:false}],ordering:'STUDENT_ASC'},
'/api/v1/exit-interviews':{...empty,items:[{id:'exit',student,academic_year:year,status:'SUBMITTED',updated_at:'2026-10-07T00:00:00Z'}],ordering:'NEWEST_SUBMITTED'},
'/api/v1/exit-interviews/opportunities':{...empty},
'/api/v1/availability/providers': {...empty, items: [{...student,full_name:'Maria Santos',role:'COUNSELOR',email:'maria@example.test',is_active:true}]},
'/api/v1/resources/management':{...empty,items:[{id:'resource',title:'Resource',kind:'EXTERNAL_LINK',category:'GENERAL',audience:'PUBLIC',status:'DRAFT',display_order:1,updated_at:'2026-10-07T00:00:00Z'}],ordering:'TITLE_ASC'},
'/api/v1/announcements/management/long':{id:'long',title:'A'.repeat(120),body_markdown:'Text',status:'DRAFT',audience:'PUBLIC',created_by:student,updated_by:student,updated_at:'2026-10-07T00:00:00Z',is_pinned:false,created_at:'2026-10-07T00:00:00Z'},
'/api/v1/call-slips':empty,
'/api/v1/referrals/long':{id:'long',reference_code:'REF-01',actions:[],student,form_revision:{official_code:'TEST',official_revision:'1'},student_name_snapshot:'Maria',course_year_block_snapshot:'BSIT / 4',referred_on:'2026-10-07',received_at:null,created_at:'2026-10-07T00:00:00Z',updated_at:'2026-10-07T00:00:00Z',recorded_by:null,referrer_name:'Example',reason:'https://example.test/'+ 'a'.repeat(240),status_note:'',voided_at:null,void_reason:'',voided_by:null},
};
