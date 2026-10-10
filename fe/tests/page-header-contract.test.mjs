import assert from "node:assert/strict";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { inspectHeaderContracts } from "./support/page-header-contract.mjs";

const root = fileURLToPath(new URL("../src", import.meta.url));
test("every actual header and forwarding wrapper obeys the semantic action contract", () => {
  const configPath = fileURLToPath(new URL("../tsconfig.json", import.meta.url));
  const config = ts.readConfigFile(configPath, ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, path.dirname(configPath));
  const result = inspectHeaderContracts(ts.createProgram(parsed.fileNames, parsed.options), root);
  assert.ok(result.compositions > 150, "scan all usage sites, including headers without PageAction imports");
  assert.ok(result.wrappers >= 15, "discover forwarding wrappers by structure, not their names");
  assert.deepEqual(result.issues, []);
});

function fixture(source, extra = {}) {
  const base = "/fixture/src";
  const files = new Map(Object.entries({
    "components/ui/page-header.tsx": "export function PageHeader(props) { return null; } export const pageBackLinkClass = 'shared';",
    "components/ui/page-action.tsx": "export function PageAction(props) { return null; } export function PageActionLink(props) { return null; } export function PageActionGroup(props) { return null; }",
    "components/ui/dialog.tsx": "export function Dialog(props){return null;} export function DialogTrigger(props){return null;}",
    "components/ui/icon-action.tsx": "export function IconAction(props){return <button aria-label={props.label}/>;}",
    "components/ui/panel.tsx": "export function PanelHeader(props) { return null; }",
    "features/example.tsx": `import {PageHeader as Header, pageBackLinkClass} from '../components/ui/page-header'; import {PageAction as Command, PageActionGroup as Group} from '../components/ui/page-action'; import {PanelHeader} from '../components/ui/panel'; ${source}`,
    ...extra,
  }).map(([f, s]) => [`${base}/${f}`, s]));
  const host = ts.createCompilerHost({});
  host.getSourceFile = (f) => files.has(f) ? ts.createSourceFile(f, files.get(f), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX) : undefined;
  host.fileExists = (f) => files.has(f);
  host.readFile = (f) => files.get(f);
  host.resolveModuleNames = (names, containing) => names.map((name) => {
    const f = `${path.resolve(path.dirname(containing), name)}.tsx`;
    return files.has(f) ? { resolvedFileName: f, extension: ts.Extension.Tsx } : undefined;
  });
  const program = ts.createProgram([...files.keys()], { noLib: true, jsx: ts.JsxEmit.Preserve }, host);
  return inspectHeaderContracts(program, base).issues;
}
for (const [name, source, expected] of [
  ["raw button", "function Page(){return <Header title='Records' actions={<button>Edit</button>}/>;}", /noncanonical button/],
  ["raw link", "function Page(){return <Header title='Records' actions={<a href='/edit'>Edit</a>}/>;}", /noncanonical a/],
  ["metadata in action slot", "function Page(){return <Header title='Records' actions={<span>Submitted today</span>}/>;}", /noncanonical span/],
  ["status metadata disguised as feedback", "function Page(){return <Header title='Records' actions={<p role='status'>Submitted today</p>}/>;}", /noncanonical p/],
  ["standalone alert in actions", "function Page(){return <Header title='Records' actions={<p role='alert'>Submitted today</p>}/>;}", /must accompany/],
  ["missing label", "function Page(){return <Header title='Records' actions={<Command icon={Icon}/>}/>;}", /visible label/],
  ["empty label branch", "function Page(){return <Header title='Records' actions={<Command icon={Icon} label={busy ? 'Loading' : ''}/>}/>;}", /visible label/],
  ["renderer override", "function Button(props){return <button/>;} function Page(){return <Header title='Records' actions={<Command icon={Icon} label='Edit' as={Button}/>}/>;}", /preserve shared navigation/],
  ["icon-only primitive", "import {IconAction} from '../components/ui/icon-action'; function Page(){return <Header title='Records' actions={<IconAction label='Download'/>}/>;}", /noncanonical button/],
  ["disguised dialog", "function Dialog(){return <button>Download</button>;} function Page(){return <Header title='Records' actions={<Dialog/>}/>;}", /noncanonical button/],
  ["hidden label", "function Page(){return <Header title='Records' actions={<Command icon={Icon} label='Edit' className='sm:sr-only'/>}/>;}", /cannot be hidden/],
  ["arbitrary forwarding wrapper", "function Frame({commands}){return <Header title='Records' actions={commands}/>;} function Page(){return <Frame commands={<button>Edit</button>}/>;}", /noncanonical button/],
  ["conditional action component", "function Download(){return busy ? null : <button aria-label='Download'>↓</button>;} function Page(){return <Header title='Records' actions={<Download/>}/>;}", /noncanonical button/],
  ["back in actions", "function Page(){return <Header title='Records' actions={<a href='/records'>Back to Records</a>}/>;}", /noncanonical a/],
  ["help in back", "function Help(){return <button>Help</button>;} function Page(){return <Header title='Records' back={<Help/>}/>;}", /non-navigation button/],
  ["command in metadata", "function Fact(){return <Command icon={Icon} label='Edit'/>;} function Page(){return <Header title='Records' meta={<Fact/>}/>;}", /misplaced in meta/],
  ["repeated heading", "function Page(){return <><Header title='Records'/><PanelHeader title='Records'/></>;}", /repeats page title/],
  ["back arrow and label", "function Page(){return <Header title='Records' back={<a href='/records' className={pageBackLinkClass}>← Records</a>}/>;}", /arrow must be decoration/],
]) test(`negative: detects ${name}`, () => assert.ok(fixture(source).some((issue) => expected.test(issue))));

test("negative: follows an imported alias through a re-export, without PageAction imports at its header", () => {
  const issues = fixture("import {Save as Export} from './barrel'; function Page(){return <Header title='Records' actions={<Export/>}/>;}", {
    "features/barrel.tsx": "export {Download as Save} from './download';",
    "features/download.tsx": "export function Download(){return <button>Download</button>;}",
  });
  assert.ok(issues.some((issue) => /noncanonical button/.test(issue)));
});

test("positive: aliases, forwarding, grouped conditional commands, dialog triggers and alert feedback", () => {
  const issues = fixture("import {Dialog, DialogTrigger} from '../components/ui/dialog'; function Frame({tools,meta}){return <Header title='Records' actions={tools} meta={meta}/>;} function Page(){return <><Frame meta={<span>Submitted</span>} tools={<div><Group>{ready ? <DialogTrigger asChild><Command icon={Icon} label='Edit'/></DialogTrigger> : null}<Dialog><button>Confirm</button></Dialog><p role='alert'>Download failed</p></Group></div>}/><PanelHeader title='Results'/></>;}");
  assert.deepEqual(issues, []);
});
