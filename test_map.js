import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch({headless: 'new'});
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('BROWSER LOG:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  
  await page.goto('http://localhost:3000/');
  await new Promise(r => setTimeout(r, 4000));
  
  const mapHeight = await page.evaluate(() => {
    const map = document.querySelector('.leaflet-container');
    return map ? map.clientHeight : -1;
  });
  
  console.log('Map Height:', mapHeight);
  await browser.close();
})();
