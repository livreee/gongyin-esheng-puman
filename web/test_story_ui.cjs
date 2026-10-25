/* Browser regression: isolated saves and local fake model, never a paid API. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const http=require('node:http');
const {spawn}=require('node:child_process');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.PLAYWRIGHT_PATH || 'C:/Users/mayzhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');

(async()=>{
  const root=path.resolve(__dirname,'..');
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'puman-stories-'));
  const modelInputs=[];
  const model=http.createServer((req,res)=>{
    let body='';req.on('data',chunk=>body+=chunk);req.on('end',()=>{
      const sent=JSON.parse(body),context=JSON.parse(sent.messages[1].content);
      modelInputs.push(context);
      res.writeHead(200,{'Content-Type':'application/json'});
      res.end(JSON.stringify({choices:[{message:{content:JSON.stringify({title:'扑满想对你说',
        message:'我记住了你的'+context.completed+'个打卡印记，第'+context.day+'步也会陪你走。',
        action:context.today_completed?'今天安心休息。':'读读今天的小故事。',risk_note:'ignored'})}}]}));
    });
  });
  await new Promise(resolve=>model.listen(0,'127.0.0.1',resolve));
  const reserved=http.createServer();await new Promise(resolve=>reserved.listen(0,'127.0.0.1',resolve));
  const port=reserved.address().port;await new Promise(resolve=>reserved.close(resolve));
  const base='http://127.0.0.1:'+port;
  const child=spawn(process.env.PYTHON || 'python',['-u','web/server.py'],{cwd:root,windowsHide:true,
    env:{...process.env,HOST:'127.0.0.1',PORT:String(port),DB_PATH:path.join(temp,'test.sqlite3'),
      LOCALAPPDATA:temp,LLM_API_KEY:'local-test-only',LLM_BASE_URL:'http://127.0.0.1:'+model.address().port,
      LLM_MODEL:'local-test',LLM_TIMEOUT:'2',PUBLIC_ORIGIN:'',RENDER_EXTERNAL_URL:''}});
  let browser;
  try{
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('server timeout')),12000);
      child.stdout.on('data',chunk=>{if(chunk.toString().includes('running at')){clearTimeout(timer);resolve();}});
      child.stderr.on('data',chunk=>process.stderr.write(chunk));child.once('error',reject);
    });
    browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
    for(const width of [320,390,768]){
      const context=await browser.newContext({viewport:{width,height:900},isMobile:width<500,hasTouch:width<500});
      const page=await context.newPage(),errors=[],requests=[];
      page.on('pageerror',error=>errors.push(error.message));
      page.on('request',request=>{if(request.url().endsWith('/api/ai/coach'))requests.push(request.postDataJSON());});
      await page.goto(base+'/h5.html#/choose');
      await page.waitForFunction(()=>!hydrationPending);
      assert.equal(await page.locator('.line-card').count(),7);
      assert.deepEqual(await page.evaluate(()=>Object.values(LINES).map(line=>line.days.length)),[21,21,21,21,21,21,21]);
      assert.equal(await page.evaluate(()=>Object.keys(LINES).indexOf('custom')),5);
      assert.equal(await page.evaluate(()=>Object.values(HOTSPOTS_2026).flat().length),19);
      await page.evaluate(()=>{S.completed.home=[1];S.lineRecords.home=[{line:'home',day:1,amount:25,from:'每日剧情任务'}];chooseLine('retirement');});
      await page.waitForURL('**#/home');
      await page.evaluate(()=>pigTalk());
      assert.match(await page.locator('#pigBubble').textContent(),/0个打卡/);
      assert.equal(await page.locator('#feature-ai-companion input, #feature-ai-companion textarea').count(),0);
      await page.evaluate(()=>doTask('answer',1));
      await page.waitForFunction(()=>S.aiCoaches.retirement[1]?.contextKey===coachContextKey('retirement',1));
      assert.match(await page.locator('#feature-ai-companion').textContent(),/1个打卡/);
      await page.evaluate(()=>answerDaily(DAILY_QUIZ[(S.day+lineIdx())%DAILY_QUIZ.length].ans));
      assert.equal(await page.evaluate(()=>S.rewards.quizzes['retirement:1'].correct),true);
      await page.waitForFunction(()=>!syncInFlight);
      await page.evaluate(()=>syncState());
      await page.reload();await page.waitForFunction(()=>!hydrationPending);
      assert.deepEqual(await page.evaluate(()=>S.completed.retirement),[1]);
      assert.equal(await page.evaluate(()=>S.lineRecords.home[0].amount),25);
      assert.ok(await page.evaluate(()=>S.lineRecords.retirement[0].completedAt));
      assert.equal(await page.evaluate(()=>S.rewards.quizzes['retirement:1'].correct),true);
      // Late responses may populate their own cache, but may never speak on a different line.
      let release,arrived;
      const hold=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>arrived=resolve);
      await page.route('**/api/ai/coach',async route=>{arrived();await hold;await route.fulfill({json:{ok:true,provider:'llm',coach:{title:'late',message:'不应出现在学习线的旧消息',action:'',risk_note:''}}});});
      await page.evaluate(()=>{setCurrentLineDay(2);renderHome();void pigTalk();});
      await seen;await page.evaluate(()=>chooseLine('solo'));release();
      await page.waitForFunction(()=>coachRequests.size===0);
      assert.doesNotMatch(await page.locator('#pigBubble').textContent(),/不应出现在/);
      await page.unroute('**/api/ai/coach');
      const endings=await page.evaluate(()=>{
        const days=Array.from({length:21},(_,i)=>i+1);
        S.line='retirement';S.day=21;S.completed.retirement=days;
        S.lineRecords.retirement=[];S.challenges.retirement=[];S.rewards.quizzes={};
        const kinds=[journeyEnding().kind];
        S.challenges.retirement=days.slice(0,7);kinds.push(journeyEnding().kind);
        for(const day of days.slice(0,7))S.rewards.quizzes['retirement:'+day]={correct:true};
        kinds.push(journeyEnding().kind);
        S.lineRecords.retirement=[{day:1,amount:10,completedAt:'2026-10-01T10:00:00Z'},{day:2,amount:10,completedAt:'2026-10-04T10:00:00Z'}];
        kinds.push(journeyEnding().kind);
        // Same amount cannot decide a different ending; other lines cannot contribute.
        S.lineRecords.retirement=[];S.challenges.retirement=[];S.rewards.quizzes={'home:1':{correct:true}};
        kinds.push(journeyEnding().kind);
        go('#/grad');return kinds;
      });
      assert.deepEqual(endings,['gentle','explorer','guardian','return','gentle']);
      await page.waitForURL('**#/grad');
      assert.match(await page.locator('#gradContent').textContent(),/个人养老金/);
      assert.match(await page.locator('#gradContent').textContent(),/非产品购买页/);
      const href=await page.locator('.completion-explore').getAttribute('href');
      assert.equal(new URL(href).hostname,'m.icbc.com.cn');assert.equal(new URL(href).search,'');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      if(width===390)await page.screenshot({path:path.join(temp,'retirement-ending-mobile.png'),fullPage:true,animations:'disabled'});
      // All seven lines have a complete, goal-specific ending and service explanation.
      assert.equal(await page.evaluate(()=>Object.keys(LINES).every(line=>{
        S.line=line;S.completed[line]=Array.from({length:21},(_,i)=>i+1);
        return !!journeyEnding().scene && officialServiceGuide(line).length===2 && completionHTML().includes('endingTitle');
      })),true);
      for(const request of requests)assert.deepEqual(Object.keys(request).sort(),['completed_days','day']);
      assert.deepEqual(errors,[]);
      console.log(JSON.stringify({width,retirementSaved:true,oldProgressPreserved:true,checkinOnly:true,fourEndings:true}));
      await page.waitForFunction(()=>!syncInFlight && !syncPending && coachRequests.size===0);
      await page.evaluate(()=>{clearTimeout(syncTimer);return syncState();});
      await context.close();
    }
    const offline=await browser.newPage({viewport:{width:390,height:844}});
    await offline.goto(pathToFileURL(path.join(root,'web/index.html')).href+'#/home');
    await offline.evaluate(()=>pigTalk());
    assert.match(await offline.locator('#feature-ai-companion').textContent(),/基础陪伴/);
    assert.equal(await offline.evaluate(()=>S.aiCoaches.home[1].provider),'rules');
    await offline.close();
    for(const context of modelInputs){
      assert.deepEqual(Object.keys(context).sort(),['completed','completed_days','day','journey_streak','participation_state','remaining','today_completed']);
    }
    assert.ok(modelInputs.length>=6);
    console.log(JSON.stringify({offlineFallback:true,modelPrivacy:true,screenshot:path.join(temp,'retirement-ending-mobile.png')}));
  }finally{
    if(browser)await browser.close();child.kill();await new Promise(resolve=>model.close(resolve));
  }
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
