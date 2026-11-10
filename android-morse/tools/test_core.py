from pathlib import Path
import ast,json,subprocess,sys
R=Path(__file__).resolve().parents[1]
config=json.loads((R/'.toolchain/environment.json').read_text(encoding='utf-8'))
java=Path(config['java'])/'bin'
data={}
src=R.parent/'outputs/morse-ai/morse_table.py'
for node in ast.parse(src.read_text(encoding='utf-8')).body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ['KANA','MARKS','DIGITS','SYMBOLS'] for t in node.targets):data.update(ast.literal_eval(node.value))
assert len(data)==65
folder=R/'core-tests/build';folder.mkdir(exist_ok=True)
expected=folder/'expected.tsv';expected.write_text('\n'.join(k+'\t'+v for k,v in data.items()),encoding='utf-8')
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(folder),str(R/'app/src/main/java/jp/local/wabun/JapaneseNumbers.java'),str(R/'app/src/main/java/jp/local/wabun/MorseCodec.java'),str(R/'app/src/main/java/jp/local/wabun/TextInput.java'),str(R/'app/src/main/java/jp/local/wabun/OpticalSignal.java'),str(R/'core-tests/CoreTest.java')],check=True)
r=subprocess.run([str(java/'java.exe'),'-cp',str(folder),'CoreTest',str(expected),str(R/'test-data')],capture_output=True,text=True,encoding='utf-8',errors='replace')
(R/'core-tests/result.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout+r.stderr);sys.exit(r.returncode)
