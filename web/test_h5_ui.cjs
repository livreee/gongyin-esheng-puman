const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const net=require('node:net');
const {chromium}=require('C:/Users/mayzhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async()=>{
  const listener=net.createServer();
  await new Promise(resolve=>listener.listen(0,'127.0.0.1',resolve));
  const port=listener.address().port;
  await new Promise(resolve=>listener.close(resolve));
  const base='http://127.0.0.1:'+port;
  const child=spawn('D:/ana/python.exe',['-u','web/server.py'],{cwd:'D:/2026工行杯',windowsHide:true,
    env:{...process.env,HOST:'127.0.0.1',PORT:String(port),DB_PATH:'D:/2026工行杯/.h5-test-temp/h5.sqlite3',
      TEMP:'D:/2026工行杯/.h5-test-temp',TMP:'D:/2026工行杯/.h5-test-temp',LLM_API_KEY:'',PUBLIC_ORIGIN:'',RENDER_EXTERNAL_URL:''}});
  let browser;
  try{
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('server timeout')),10000);child.stdout.on('data',chunk=>{if(chunk.toString().includes('running at')){clearTimeout(timer);resolve();}});child.once('error',reject);});
    browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
    for(const width of [320,390,768]){
      const context=await browser.newContext({viewport:{width,height:844},isMobile:width<500,hasTouch:width<500});
      const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
      await page.goto(base+'/h5.html?campaign=demo#/start');
      await page.waitForURL('**/index.html?mode=h5&campaign=demo#/start');
      assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('h5-mode')&&PumanH5.isEmbedded),true);
      const frame=JSON.parse(JSON.stringify(await page.locator('.phone').evaluate(element=>({width:element.getBoundingClientRect().width,border:getComputedStyle(element).borderLeftWidth,margin:getComputedStyle(element).marginLeft}))));
      assert.deepEqual(frame,{width,border:'0px',margin:'0px'});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.evaluate(()=>PumanH5Receive({source:'icbc-app',type:'puman.safeArea',detail:{top:30,bottom:22,right:4,left:4}}));
      assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--app-safe-top')),'30px');
      await page.evaluate(()=>go('#/quiz'));await page.evaluate(()=>PumanH5Receive({source:'icbc-app',type:'puman.back'}));await page.waitForURL('**#/start');
      assert.deepEqual(errors,[]);
      if(width===390)await page.screenshot({path:'D:/2026工行杯/screenshots/h5-start-mobile.png',fullPage:true,animations:'disabled'});
      await context.close();console.log(JSON.stringify({width,h5:true,fullWidth:true,safeArea:true,bridgeBack:true}));
    }
    const context=await browser.newContext({viewport:{width:768,height:844}}),page=await context.newPage();
    await page.goto(base+'/index.html#/start');assert.equal(await page.evaluate(()=>document.documentElement.classList.contains('h5-mode')),false);assert.ok((await page.locator('.phone').boundingBox()).width<500);
    console.log(JSON.stringify({webModeUnchanged:true}));await context.close();
  }finally{if(browser)await browser.close();child.kill();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
