import { service } from './ui-hierarchy-fixtures.mjs';
import { homeWorld } from './ux15-home-fixtures.mjs';
const empty = {items:[],page:1,page_size:20,has_next:false};
const year = {id:'synthetic-year',label:'2026–2027'};
export const featureCases = [
  ['booking','/portal/appointments/book','Ways to get support','service-catalog-3d'],
  ['messages','/portal/messages','No messages yet.','guidance-messages-3d'],
  ['inventory','/portal/inventory','Start Individual Inventory','individual-inventory-3d'],
  ['good-moral','/portal/good-moral/request','Request Good Moral Certificate','good-moral-3d'],
  ['exit','/portal/exit-interviews','The Guidance and Counseling Office has opened an Exit Interview for you.','exit-interview-3d'],
  ['tracer','/portal/graduate-tracer','Start Graduate Tracer Survey','graduate-tracer-3d'],
];
export function featureWorld(name, mode='intro') {
  const w=homeWorld({lifecycle:name==='tracer'?'GRADUATED':'CURRENT'});
  w.account.exit_interview_workspace_available=true;
  const parent=w.handler;
  w.handler=async args=>{
    const {pathname,reply}=args;
    if(mode==='error' && [
      '/api/v1/inventory/me/status','/api/v1/exit-interviews/me/status','/api/v1/graduate-tracer/me',
      '/api/v1/good-moral/me/academic-context','/api/v1/guidance-messages/threads','/api/v1/appointments/booking/services',
    ].includes(pathname)) {await reply({error:{code:'synthetic_unavailable',message:'Synthetic'}},503);return true;}
    if(pathname==='/api/v1/appointments/booking/services') {await reply({...empty,items:[service],has_next:true});return true;}
    if(pathname==='/api/v1/inventory/me/status') {await reply({academic_year:year,status:'MISSING',correction_pending:false});return true;}
    if(pathname==='/api/v1/inventory/me/history') {await reply(empty);return true;}
    if(pathname==='/api/v1/exit-interviews/me/status') {await reply({academic_year:year,current_record:null,has_records:false,can_start:mode!=='blocked',can_edit_current:false,inventory_submitted:mode!=='blocked',opportunity:{id:'synthetic-opportunity',status:'OPEN',source:'MANUAL',academic_year:year},graduation_good_moral_blocked:false});return true;}
    if(pathname==='/api/v1/exit-interviews/me') {await reply(empty);return true;}
    if(pathname==='/api/v1/graduate-tracer/me') {await reply({error:{code:'graduate_tracer_not_found',message:'Synthetic'}},404);return true;}
    if(pathname==='/api/v1/good-moral/me/academic-context') {await reply({status:mode==='blocked'?'INVENTORY_REQUIRED':'ELIGIBLE',academic_classification:'BACHELORS',year_level:2});return true;}
    if(pathname==='/api/v1/guidance-messages/threads') {await reply(empty);return true;}
    return parent(args);
  };
  return w;
}
