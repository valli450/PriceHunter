"""Deep page structure analysis"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.bestbuy.com/top-deals", wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(4000)
        
        # Find product cards
        structure = await page.evaluate("""
            () => {
                // Find actual product cards - look for elements with multiple children containing prices and titles
                const allDivs = document.querySelectorAll('div');
                const candidates = [];
                
                allDivs.forEach(div => {
                    const text = div.innerText || '';
                    const hasDollar = text.includes('$');
                    const hasTitle = text.length > 30;
                    const children = div.children.length;
                    
                    if (hasDollar && hasTitle && children > 0) {
                        const titleEl = div.querySelector('h3, h4, [class*="title"]');
                        const link = div.querySelector('a[href*="/site/"]');
                        
                        if (titleEl && link) {
                            const title = titleEl.innerText.trim();
                            if (title.length > 10) {
                                candidates.push({
                                    className: div.className.substring(0, 100),
                                    tagName: div.tagName,
                                    title: title.substring(0, 50),
                                    links: link.href.substring(0, 80),
                                    childCount: children,
                                    textLen: text.length,
                                });
                            }
                        }
                    }
                });
                
                return candidates.slice(0, 15);
            }
        """)
        
        print("Product card candidates:")
        for c in structure:
            print(f"  class={c['className']}")
            print(f"    title={c['title']}")
            print(f"    link={c['links']}")
            print(f"    children={c['childCount']}")
            print()

if __name__ == "__main__":
    asyncio.run(main())
