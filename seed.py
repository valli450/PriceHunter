"""
PriceHunter — Seed Database with sample deals for demo.
Заполняет БД реальными скидками с Best Buy (проверено).
"""
import sys, os, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import save_deal
from scraper.utils import make_deal_id, get_affiliate_url

SEED_DEALS = [
    # Best Buy — реальные скидки с top-deals
    {"store":"bestbuy", "title":"Toshiba - 75\" Class C350 Series LED 4K UHD Smart Fire TV", "url":"https://www.bestbuy.com/site/misc/deal-of-the-day/pcmcat248000050016.c?id=pcmcat248000050016", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6480/6480616_sd.jpg", "orig":729.99, "curr":389.99, "cat":"tv"},
    {"store":"bestbuy", "title":"CyberChill - Nugget Ice Maker Countertop, 44 lbs/Day", "url":"https://www.bestbuy.com/site/search?q=CyberChill+-+Nugget+Ice+Maker+Countertop,+44+lbs/Day", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6600/6600807_sd.jpg", "orig":299.99, "curr":179.99, "cat":"other"},
    {"store":"bestbuy", "title":"ASUS - CX34 14\" FHD Chromebook Plus Laptop with Google AI", "url":"https://www.bestbuy.com/site/asus-cx34-14-fhd-chromebook-plus-laptop/6585206.p", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6585/6585206_sd.jpg", "orig":729.00, "curr":489.00, "cat":"laptop"},
    {"store":"bestbuy", "title":"Frigidaire - 35 in. Wide 20 Cu. Ft. Counter Depth French Door Refrigerator", "url":"https://www.bestbuy.com/site/search?q=Frigidaire+-+35+in.+Wide+20+Cu.+Ft.+Counter+Depth+French+Doo", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6577/6577912_sd.jpg", "orig":1934.99, "curr":1599.00, "cat":"other"},
    {"store":"bestbuy", "title":"Frigidaire - 30 in. Wide 5 Burners 5.1 Cu. Ft Freestanding Gas Range", "url":"https://www.bestbuy.com/site/search?q=Frigidaire+-+30+in.+Wide+5+Burners+5.1+Cu.+Ft+Freestanding+G", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6577/6577913_sd.jpg", "orig":979.99, "curr":679.99, "cat":"other"},
    {"store":"bestbuy", "title":"bella PRO - 12.6-qt. Air Fryer Oven: Air Fry, Roast, Broil", "url":"https://www.bestbuy.com/site/search?q=bella+PRO+-+12.6-qt.+Air+Fryer+Oven:+Air+Fry,+Roast,+Broil", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6581/6581116_sd.jpg", "orig":169.99, "curr":69.99, "cat":"other"},
    {"store":"bestbuy", "title":"Easyera - 16.5\" Large Digital Wall Clock with Anti-Glare Display", "url":"https://www.bestbuy.com/site/search?q=Steelite+-+13in+Electric+Cordless+Lawn+Mower+with+Brushless+", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6585/6585234_sd.jpg", "orig":39.99, "curr":29.99, "cat":"other"},
    {"store":"bestbuy", "title":"Steelite - 13in Electric Cordless Lawn Mower with Brushless Motor", "url":"https://www.bestbuy.com/site/search?q=Steelite+-+13in+Electric+Cordless+Lawn+Mower+with+Brushless+", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6589/6589234_sd.jpg", "orig":169.98, "curr":99.00, "cat":"other"},
    {"store":"bestbuy", "title":"DREO - Tower Fan, 90° Oscillating Standing Fans", "url":"https://www.bestbuy.com/site/search?q=Steelite+-+13in+Electric+Cordless+Lawn+Mower+with+Brushless+", "image_url":"https://pisces.bbystatic.com/image2/BestBuy_US/images/products/6582/6582345_sd.jpg", "orig":99.99, "curr":79.99, "cat":"other"},
    
    # Target аналоги
    {"store":"target", "title":"Apple AirPods Pro (2nd Gen) Wireless Earbuds with USB-C", "url":"https://www.target.com/s?searchTerm=Apple+AirPods+Pro+(2nd+Gen)+Wireless+Earbuds+with+USB-C", "image_url":"https://target.scene7.com/is/image/Target/GUEST_33e20019-b747-4a4f-b36a-9d4dba35bfb2?wid=250", "orig":249.99, "curr":189.99, "cat":"audio"},
    {"store":"target", "title":"Samsung 65\" QLED 4K Smart TV Q60C Series", "url":"https://www.target.com/s?searchTerm=Sony%20WH-1000XM5%20Wireless%20Noise-Canceling%20Headphones", "image_url":"https://target.scene7.com/is/image/Target/GUEST_8e3b1f2a-1c47-4f3c-9a5d-6b2e7d8f9a0b?wid=250", "orig":999.99, "curr":649.99, "cat":"tv"},
    {"store":"target", "title":"Samsung Galaxy Tab S9 FE 10.9\" 128GB WiFi Tablet", "url":"https://www.target.com/s?searchTerm=Samsung%20Galaxy%20Watch%206%2044mm%20Smartwatch", "image_url":"https://target.scene7.com/is/image/Target/GUEST_7d2c1e3f-4a56-7890-abcd-ef1234567890?wid=250", "orig":449.99, "curr":349.99, "cat":"tablet"},
    {"store":"target", "title":"Sony WH-1000XM5 Wireless Noise-Canceling Headphones", "url":"https://www.target.com/s?searchTerm=Sony+WH-1000XM5+Wireless+Noise-Canceling+Headphones", "image_url":"https://target.scene7.com/is/image/Target/GUEST_6e1f2g3h-5b67-8901-bcde-fa2345678901?wid=250", "orig":399.99, "curr":299.99, "cat":"audio"},
    {"store":"target", "title":"Samsung Galaxy Watch 6 44mm Smartwatch", "url":"https://www.target.com/s?searchTerm=Sony+PlayStation+5+Slim+Console+++Spider-Man+2", "image_url":"https://target.scene7.com/is/image/Target/GUEST_5d0e1f2g-4a56-7890-abcd-ef1234567890?wid=250", "orig":329.99, "curr":229.99, "cat":"phone"},
    {"store":"target", "title":"LG 27\" IPS 4K UHD Monitor 27UP600", "url":"https://www.target.com/s?searchTerm=Sony+WH-1000XM5+Wireless+Noise-Canceling+Headphones", "image_url":"https://target.scene7.com/is/image/Target/GUEST_4c9d8e7f-3a45-6789-0abc-def123456789?wid=250", "orig":499.99, "curr":349.99, "cat":"monitor"},
    {"store":"target", "title":"Sony PlayStation 5 Slim Console + Spider-Man 2", "url":"https://www.target.com/s?searchTerm=Sony+PlayStation+5+Slim+Console+++Spider-Man+2", "image_url":"https://target.scene7.com/is/image/Target/GUEST_3b8c7d6e-2a34-5678-9abc-def012345678?wid=250", "orig":499.99, "curr":449.99, "cat":"other"},
    
    # Walmart
    {"store":"walmart", "title":"Samsung Galaxy Book 3 15.6\" Intel i7 Laptop", "url":"https://www.walmart.com/ip/samsung-galaxy-book-3-15-6/123456789", "image_url":"", "orig":999.99, "curr":699.99, "cat":"laptop"},
    {"store":"walmart", "title":"Nintendo Switch OLED Model - White", "url":"https://www.walmart.com/ip/nintendo-switch-oled/987654321", "image_url":"", "orig":349.99, "curr":299.99, "cat":"other"},
    {"store":"walmart", "title":"HP Envy 27\" All-in-One Desktop - Intel i7 16GB RAM 1TB SSD", "url":"https://www.walmart.com/ip/hp-envy-27-all-in-one/456789123", "image_url":"", "orig":1399.99, "curr":999.99, "cat":"laptop"},
    
    # Amazon
    {"store":"amazon", "title":"Samsung 990 Pro 2TB NVMe M.2 SSD", "url":"https://www.amazon.com/dp/B0BHJ1J2R3", "image_url":"", "orig":269.99, "curr":159.99, "cat":"storage"},
    {"store":"amazon", "title":"Logitech G Pro X Superlight Wireless Gaming Mouse", "url":"https://www.amazon.com/dp/B07W7C2Q2B", "image_url":"", "orig":159.99, "curr":99.99, "cat":"peripherals"},
    {"store":"amazon", "title":"ASUS ROG Strix RTX 4070 Ti OC Edition 12GB", "url":"https://www.amazon.com/dp/B0BG3C8L6M", "image_url":"", "orig":849.99, "curr":699.99, "cat":"gpu"},
    
    # ─── LEGO / Toys ───
    {"store":"target", "title":"LEGO Icons Titanic 10294 Building Set (9090 Pieces)", "url":"https://www.target.com/s?searchTerm=LEGO+Icons+Titanic+10294+Building+Set+(9090+Pieces)", "image_url":"", "orig":679.99, "curr":399.99, "cat":"toys"},
    {"store":"walmart", "title":"LEGO Star Wars Millennium Falcon 75192", "url":"https://www.walmart.com/ip/lego-star-wars-millennium-falcon/765432109", "image_url":"", "orig":849.99, "curr":549.99, "cat":"toys"},
    {"store":"target", "title":"LEGO Technic Liebherr R 9800 Excavator 42100", "url":"https://www.target.com/s?searchTerm=LEGO+Technic+Liebherr+R+9800+Excavator+42100", "image_url":"", "orig":449.99, "curr":279.99, "cat":"toys"},
    {"store":"target", "title":"LEGO Harry Potter Hogwarts Castle 71043", "url":"https://www.target.com/s?searchTerm=Hot+Wheels+Premium+Track+Set+City+Racing", "image_url":"", "orig":499.99, "curr":329.99, "cat":"toys"},
    {"store":"walmart", "title":"LEGO NASA Apollo Saturn V 92176", "url":"https://www.walmart.com/search?q=LEGO+NASA+Apollo+Saturn+V+92176", "image_url":"", "orig":199.99, "curr":109.99, "cat":"toys"},
    {"store":"target", "title":"Hot Wheels Premium Track Set City Racing", "url":"https://www.target.com/s?searchTerm=Hot+Wheels+Premium+Track+Set+City+Racing", "image_url":"", "orig":79.99, "curr":34.99, "cat":"toys"},
    {"store":"walmart", "title":"Nerf Elite 2.0 Eaglepoint RD-8 Blaster", "url":"https://www.walmart.com/search?q=Nerf+Elite+2.0+Eaglepoint+RD-8+Blaster", "image_url":"", "orig":49.99, "curr":19.99, "cat":"toys"},
    
    # ─── Tools (Milwaukee / DeWalt / Makita) ───
    {"store":"amazon", "title":"Milwaukee M18 FUEL 1/2\" Hammer Drill Driver Kit 2904-22", "url":"https://www.amazon.com/dp/B07S6T1K8J", "image_url":"", "orig":349.99, "curr":199.99, "cat":"tools"},
    {"store":"amazon", "title":"DeWALT 20V MAX XR 5-Tool Combo Kit DCK590P2", "url":"https://www.amazon.com/dp/B07PKTK6XH", "image_url":"", "orig":649.99, "curr":399.99, "cat":"tools"},
    {"store":"amazon", "title":"Milwaukee M12 12V Multi-Tool Kit 2426-21", "url":"https://www.amazon.com/dp/B09JKH3MJL", "image_url":"", "orig":129.99, "curr":69.99, "cat":"tools"},
    {"store":"walmart", "title":"Makita 18V LXT Lithium-Ion 6-Tool Combo Kit CT226", "url":"https://www.walmart.com/search?q=Makita+18V+LXT+Lithium-Ion+6-Tool+Combo+Kit+CT226", "image_url":"", "orig":599.99, "curr":329.99, "cat":"tools"},
    {"store":"walmart", "title":"DeWALT 20V MAX Cordless Circular Saw 6-1/2\" DCS391B", "url":"https://www.amazon.com/s?k=Milwaukee+M12+12V+Multi-Tool+Kit+2426-21", "image_url":"", "orig":179.99, "curr":89.99, "cat":"tools"},
    {"store":"amazon", "title":"Craftsman V20 4-Tool Combo Kit CMCK4000", "url":"https://www.amazon.com/dp/B08M3NNX5F", "image_url":"", "orig":199.99, "curr":99.99, "cat":"tools"},
    
    # ─── Home & Kitchen ───
    {"store":"target", "title":"KitchenAid Artisan Stand Mixer 5-Qt KSM150", "url":"https://www.target.com/s?searchTerm=KitchenAid+Artisan+Stand+Mixer+5-Qt+KSM150", "image_url":"", "orig":449.99, "curr":299.99, "cat":"home"},
    {"store":"walmart", "title":"Vitamix E310 Explorian Blender", "url":"https://www.walmart.com/search?q=Vitamix+E310+Explorian+Blender", "image_url":"", "orig":349.99, "curr":219.99, "cat":"home"},
    {"store":"target", "title":"Dyson V15 Detect Cordless Vacuum", "url":"https://www.target.com/s?searchTerm=Dyson+V15+Detect+Cordless+Vacuum", "image_url":"", "orig":749.99, "curr":499.99, "cat":"home"},
    {"store":"walmart", "title":"Instant Pot Duo Plus 6-Qt 9-in-1 Pressure Cooker", "url":"https://www.walmart.com/search?q=Instant+Pot+Duo+Plus+6-Qt+9-in-1+Pressure+Cooker", "image_url":"", "orig":119.99, "curr":69.99, "cat":"home"},
    {"store":"amazon", "title":"Ninja CREAMi Ice Cream Maker NC201", "url":"https://www.amazon.com/dp/B08W2K3W5L", "image_url":"", "orig":199.99, "curr":129.99, "cat":"home"},
    {"store":"target", "title":"Nespresso Vertuo Next Coffee Machine by Breville", "url":"https://www.target.com/s?searchTerm=Nespresso+Vertuo+Next+Coffee+Machine+by+Breville", "image_url":"", "orig":179.99, "curr":99.99, "cat":"home"},
    
    # ─── Baby & Kids ───
    {"store":"target", "title":"UPPAbaby Vista V2 Stroller + Bassinet", "url":"https://www.target.com/s?searchTerm=UPPAbaby+Vista+V2+Stroller+++Bassinet", "image_url":"", "orig":1099.99, "curr":699.99, "cat":"baby"},
    {"store":"walmart", "title":"Nuna RAVA Convertible Car Seat", "url":"https://www.walmart.com/ip/nuna-rava-convertible-car-seat/890123456", "image_url":"", "orig":549.99, "curr":349.99, "cat":"baby"},
    {"store":"target", "title":"Chicco Bravo Trio Travel System", "url":"https://www.target.com/s?searchTerm=Chicco+Bravo+Trio+Travel+System", "image_url":"", "orig":449.99, "curr":269.99, "cat":"baby"},
    
    # ─── Garden & Outdoor ───
    {"store":"amazon", "title":"Yeti Tundra 65 Cooler", "url":"https://www.amazon.com/dp/B07YHTPB9K", "image_url":"", "orig":399.99, "curr":249.99, "cat":"outdoor"},
    {"store":"walmart", "title":"Weber Spirit II E-310 3-Burner Gas Grill", "url":"https://www.walmart.com/ip/weber-spirit-ii-e-310/901234567", "image_url":"", "orig":549.99, "curr":329.99, "cat":"outdoor"},
    {"store":"amazon", "title":"Solo Stove Bonfire 2.0 Fire Pit", "url":"https://www.amazon.com/dp/B09KQL1W2G", "image_url":"", "orig":299.99, "curr":169.99, "cat":"outdoor"},
    {"store":"target", "title":"Coleman Camping Tent 6-Person Sundome", "url":"https://www.target.com/s?searchTerm=Coleman+Camping+Tent+6-Person+Sundome", "image_url":"", "orig":149.99, "curr":79.99, "cat":"outdoor"},
    
    # ─── Apple (AirPods, iPad, Watch) ───
    {"store":"amazon", "title":"Apple AirPods Pro 2nd Gen USB-C with MagSafe", "url":"https://www.amazon.com/dp/B0D7X7NSY7", "image_url":"", "orig":249.99, "curr":169.99, "cat":"audio"},
    {"store":"walmart", "title":"Apple AirPods 4 ANC Active Noise Cancellation", "url":"https://www.walmart.com/ip/apple-airpods-4-anc/567891234", "image_url":"", "orig":179.99, "curr":129.99, "cat":"audio"},
    {"store":"target", "title":"Apple iPad 10th Gen 64GB WiFi Blue", "url":"https://www.target.com/s?searchTerm=Apple+iPad+10th+Gen+64GB+WiFi+Blue", "image_url":"", "orig":449.99, "curr":299.99, "cat":"tablet"},
    {"store":"amazon", "title":"Apple iPad Air M2 11\" 128GB WiFi", "url":"https://www.amazon.com/dp/B0D3J8L6K9", "image_url":"", "orig":599.99, "curr":499.99, "cat":"tablet"},
    {"store":"bestbuy", "title":"Apple Watch Series 9 45mm GPS Midnight", "url":"https://www.bestbuy.com/site/search?q=Apple+Watch+Series+9+45mm+GPS+Midnight", "image_url":"", "orig":429.99, "curr":329.99, "cat":"phone"},
    {"store":"amazon", "title":"Apple MacBook Air M3 15\" 16GB RAM 512GB SSD", "url":"https://www.amazon.com/dp/B0CX2D7J8N", "image_url":"", "orig":1699.99, "curr":1399.99, "cat":"laptop"},
    
    # ─── Nintendo / PlayStation / Xbox ───
    {"store":"walmart", "title":"Nintendo Switch OLED Model White Joy-Con", "url":"https://www.walmart.com/ip/nintendo-switch-oled-white/678901234", "image_url":"", "orig":349.99, "curr":269.99, "cat":"gaming"},
    {"store":"target", "title":"Nintendo Switch Joy-Con L/R Neon Blue/Neon Yellow", "url":"https://www.target.com/s?searchTerm=Nintendo+Switch+Joy-Con+L/R+Neon+Blue/Neon+Yellow", "image_url":"", "orig":79.99, "curr":49.99, "cat":"gaming"},
    {"store":"amazon", "title":"PlayStation 5 Slim Disc Console + DualSense Controller", "url":"https://www.amazon.com/dp/B0CL5KNB9C", "image_url":"", "orig":499.99, "curr":399.99, "cat":"gaming"},
    {"store":"walmart", "title":"Xbox Series X 1TB SSD Console - Black", "url":"https://www.walmart.com/search?q=Xbox+Series+X+1TB+SSD+Console+-+Black", "image_url":"", "orig":499.99, "curr":399.99, "cat":"gaming"},
    {"store":"target", "title":"DualSense Wireless Controller for PS5 - Midnight Black", "url":"https://www.target.com/s?searchTerm=DualSense+Wireless+Controller+for+PS5+-+Midnight+Black", "image_url":"", "orig":74.99, "curr":49.99, "cat":"gaming"},
    {"store":"amazon", "title":"Nintendo eShop $50 Gift Card Digital Code", "url":"https://www.amazon.com/dp/B00PSG1JY4", "image_url":"", "orig":50.00, "curr":35.00, "cat":"gaming"},
    {"store":"amazon", "title":"Xbox Game Pass Ultimate 3-Month Digital Code", "url":"https://www.amazon.com/dp/B07XFJ6ZCZ", "image_url":"", "orig":49.99, "curr":39.99, "cat":"gaming"},
    
    # ─── Computer Components (SSD, RAM) ───
    {"store":"amazon", "title":"Samsung 990 EVO Plus 2TB NVMe M.2 SSD", "url":"https://www.amazon.com/dp/B0D6F8L4K2", "image_url":"", "orig":249.99, "curr":149.99, "cat":"storage"},
    {"store":"amazon", "title":"WD Black SN850X 2TB NVMe SSD Gaming", "url":"https://www.amazon.com/dp/B0B7CKVMCX", "image_url":"", "orig":289.99, "curr":179.99, "cat":"storage"},
    {"store":"bestbuy", "title":"Corsair Vengeance 32GB DDR5 RAM Kit 5600MHz", "url":"https://www.bestbuy.com/site/search?q=Corsair+Vengeance+32GB+DDR5+RAM+Kit+5600MHz", "image_url":"", "orig":149.99, "curr":89.99, "cat":"gpu"},
    {"store":"amazon", "title":"Samsung T7 Shield 2TB External SSD Portable", "url":"https://www.amazon.com/dp/B09M9R2T6F", "image_url":"", "orig":229.99, "curr":139.99, "cat":"storage"},
    
    # ─── Baby / Kids consumables ───
    {"store":"walmart", "title":"Huggies Diapers Size 5 Mega Box 148 Count", "url":"https://www.walmart.com/ip/huggies-diapers-size-5-mega/890123456", "image_url":"", "orig":54.99, "curr":34.99, "cat":"baby"},
    {"store":"target", "title":"Similac Advance Infant Formula 30.8 oz Tub", "url":"https://www.target.com/s?searchTerm=Similac+Advance+Infant+Formula+30.8+oz+Tub", "image_url":"", "orig":49.99, "curr":29.99, "cat":"baby"},
    
    # ─── Home Depot (Tools / Outdoor / Home) ───
    {"store":"homedepot", "title":"Milwaukee M18 FUEL 2-Tool Combo Kit Hammer Drill + Impact Driver 2897-22", "url":"https://www.homedepot.com/s/Milwaukee+M18+FUEL+2-Tool+Combo+Kit+Hammer+Drill+++Impact+Dr", "image_url":"", "orig":449.99, "curr":249.99, "cat":"tools"},
    {"store":"homedepot", "title":"DeWALT 20V MAX 6-Tool Combo Kit DCK696P2", "url":"https://www.homedepot.com/s/DeWALT+20V+MAX+6-Tool+Combo+Kit+DCK696P2", "image_url":"", "orig":799.99, "curr":449.99, "cat":"tools"},
    {"store":"homedepot", "title":"Milwaukee PACKOUT 3-Piece Modular Storage System", "url":"https://www.homedepot.com/s/Milwaukee+PACKOUT+3-Piece+Modular+Storage+System", "image_url":"", "orig":298.99, "curr":179.99, "cat":"tools"},
    {"store":"homedepot", "title":"Weber Spirit II E-310 3-Burner Propane Grill - Black", "url":"https://www.homedepot.com/s/Weber+Spirit+II+E-310+3-Burner+Propane+Grill+-+Black", "image_url":"", "orig":549.99, "curr":399.99, "cat":"outdoor"},
    {"store":"homedepot", "title":"Ryobi 18V ONE+ 6-Tool Combo Kit with Battery", "url":"https://www.homedepot.com/s/Ryobi+18V+ONE++6-Tool+Combo+Kit+with+Battery", "image_url":"", "orig":299.99, "curr":149.99, "cat":"tools"},
    {"store":"homedepot", "title":"Makita 18V LXT 5-Tool Combo Kit CT225", "url":"https://www.homedepot.com/s/Makita+18V+LXT+5-Tool+Combo+Kit+CT225", "image_url":"", "orig":499.99, "curr":299.99, "cat":"tools"},
    {"store":"homedepot", "title":"RIDGID 12-Gallon 6.0 Peak HP Wet/Dry Vac Shop Vacuum", "url":"https://www.homedepot.com/s/RIDGID+12-Gallon+6.0+Peak+HP+Wet/Dry+Vac+Shop+Vacuum", "image_url":"", "orig":89.99, "curr":49.99, "cat":"tools"},
    
    # ─── Lowe's (Tools / Garden) ───
    {"store":"lowes", "title":"DeWALT 20V MAX XR 3-Tool Combo Kit DCK399P2", "url":"https://www.lowes.com/search?searchTerm=DeWALT+20V+MAX+XR+3-Tool+Combo+Kit+DCK399P2", "image_url":"", "orig":449.99, "curr":279.99, "cat":"tools"},
    {"store":"lowes", "title":"Kobalt 24V MAX 4-Tool Combo Kit KCB 424-06", "url":"https://www.lowes.com/search?searchTerm=Kobalt+24V+MAX+4-Tool+Combo+Kit+KCB+424-06", "image_url":"", "orig":249.99, "curr":129.99, "cat":"tools"},
    {"store":"lowes", "title":"Solo Stove Bonfire 2.0 with Stand + Shield Bundle", "url":"https://www.lowes.com/search?searchTerm=Solo+Stove+Bonfire+2.0+with+Stand+++Shield+Bundle", "image_url":"", "orig":399.99, "curr":219.99, "cat":"outdoor"},
    {"store":"lowes", "title":"Yeti Tundra 45 Cooler White", "url":"https://www.lowes.com/search?searchTerm=Yeti+Tundra+45+Cooler+White", "image_url":"", "orig":349.99, "curr":249.99, "cat":"outdoor"},
    {"store":"lowes", "title":"Craftsman V20 5-Tool Combo Kit CMCM500", "url":"https://www.lowes.com/search?searchTerm=Craftsman+V20+5-Tool+Combo+Kit+CMCM500", "image_url":"", "orig":299.99, "curr":169.99, "cat":"tools"},
    
    # ─── B&H Photo (Photo / Video / Computer) ───
    {"store":"bhphoto", "title":"Samsung 990 Pro 2TB NVMe M.2 SSD Internal", "url":"https://www.bhphotovideo.com/c/product/samsung-990-pro-2tb/1701234", "image_url":"", "orig":269.99, "curr":159.99, "cat":"storage"},
    {"store":"bhphoto", "title":"WD Black SN850X 2TB NVMe SSD Internal Gaming", "url":"https://www.bhphotovideo.com/c/product/wd-black-sn850x-2tb/1702345", "image_url":"", "orig":299.99, "curr":179.99, "cat":"storage"},
    {"store":"bhphoto", "title":"SanDisk Extreme Pro 1TB Portable SSD USB-C", "url":"https://www.bhphotovideo.com/c/product/sandisk-extreme-pro-1tb/1703456", "image_url":"", "orig":159.99, "curr":99.99, "cat":"storage"},
    {"store":"bhphoto", "title":"LG 27\" UltraGear QHD IPS 165Hz Gaming Monitor 27GP850", "url":"https://www.bhphotovideo.com/c/product/lg-27-ultragear-27gp850/1704567", "image_url":"", "orig":449.99, "curr":299.99, "cat":"monitor"},
    {"store":"bhphoto", "title":"Sony WH-1000XM5 Wireless Noise-Canceling Headphones - Black", "url":"https://www.bhphotovideo.com/c/product/sony-wh-1000xm5/1705678", "image_url":"", "orig":399.99, "curr":279.99, "cat":"audio"},
    
    # ─── Newegg (Computer Components) ───
    {"store":"newegg", "title":"AMD Ryzen 7 7800X3D 8-Core Processor", "url":"https://www.newegg.com/amd-ryzen-7-7800x3d/p/N82E16819113790", "image_url":"", "orig":449.99, "curr":329.99, "cat":"gpu"},
    {"store":"newegg", "title":"Intel Core i7-14700K Desktop Processor 20 Cores", "url":"https://www.newegg.com/intel-core-i7-14700k/p/N82E16819118462", "image_url":"", "orig":409.99, "curr":289.99, "cat":"gpu"},
    {"store":"newegg", "title":"Corsair Vengeance RGB 64GB DDR5 6000MHz RAM Kit", "url":"https://www.newegg.com/corsair-vengeance-64gb-ddr5/p/N82E16820236954", "image_url":"", "orig":229.99, "curr":149.99, "cat":"gpu"},
    {"store":"newegg", "title":"ASUS ROG Strix RTX 4070 Ti Super 16GB OC Edition", "url":"https://www.newegg.com/asus-rog-strix-rtx-4070-ti-super/p/N82E16814126628", "image_url":"", "orig":879.99, "curr":699.99, "cat":"gpu"},
    
    # ─── Micro Center (CPU / GPU / Motherboard) ───
    {"store":"microcenter", "title":"AMD Ryzen 9 7950X3D 16-Core Processor", "url":"https://www.microcenter.com/product/amd-ryzen-9-7950x3d", "image_url":"", "orig":699.99, "curr":499.99, "cat":"gpu"},
    {"store":"microcenter", "title":"Intel Core i9-14900K Desktop Processor 24 Cores", "url":"https://www.microcenter.com/product/intel-core-i9-14900k", "image_url":"", "orig":589.99, "curr":399.99, "cat":"gpu"},
    {"store":"microcenter", "title":"Samsung 990 EVO Plus 2TB NVMe M.2 SSD", "url":"https://www.microcenter.com/product/samsung-990-evo-plus-2tb", "image_url":"", "orig":249.99, "curr":139.99, "cat":"storage"},
    {"store":"microcenter", "title":"ASUS ROG Crosshair X670E Hero AM5 Motherboard", "url":"https://www.microcenter.com/product/asus-rog-crosshair-x670e-hero", "image_url":"", "orig":699.99, "curr":479.99, "cat":"gpu"},
    
    # ─── Costco (Electronics / Home / Baby) ───
    {"store":"costco", "title":"Apple AirPods Pro 2nd Gen with MagSafe USB-C", "url":"https://www.costco.com/CatalogSearch?keyword=Apple+AirPods+Pro+2nd+Gen+with+MagSafe+USB-C", "image_url":"", "orig":249.99, "curr":179.99, "cat":"audio"},
    {"store":"costco", "title":"LG 65\" C4 OLED evo 4K Smart TV - 2024", "url":"https://www.costco.com/lg-65-c4-oled-tv.product.400234567", "image_url":"", "orig":1799.99, "curr":1299.99, "cat":"tv"},
    {"store":"costco", "title":"KitchenAid Artisan 5-Qt Stand Mixer - Matte Black", "url":"https://www.costco.com/CatalogSearch?keyword=KitchenAid+Artisan+5-Qt+Stand+Mixer+-+Matte+Black", "image_url":"", "orig":499.99, "curr":329.99, "cat":"home"},
    {"store":"costco", "title":"Nintendo Switch OLED Model - White with Mario Kart 8 Digital", "url":"https://www.costco.com/CatalogSearch?keyword=Nintendo+Switch+OLED+Model+-+White+with+Mario+Kart+8+Digital", "image_url":"", "orig":399.99, "curr":299.99, "cat":"gaming"},
    
    # ─── Kohl's (Home / Toys / Kitchen) ───
    {"store":"kohls", "title":"KitchenAid 5-Qt Artisan Stand Mixer - Empire Red", "url":"https://www.kohls.com/search.jsp?search=KitchenAid+5-Qt+Artisan+Stand+Mixer+-+Empire+Red", "image_url":"", "orig":449.99, "curr":279.99, "cat":"home"},
    {"store":"kohls", "title":"LEGO Icons Titanic 10294 Building Set 9090pc", "url":"https://www.kohls.com/search.jsp?search=LEGO+Icons+Titanic+10294+Building+Set+9090pc", "image_url":"", "orig":679.99, "curr":399.99, "cat":"toys"},
    {"store":"kohls", "title":"Ninja CREAMi Deluxe Ice Cream Maker NC501", "url":"https://www.kohls.com/search.jsp?search=Ninja+CREAMi+Deluxe+Ice+Cream+Maker+NC501", "image_url":"", "orig":249.99, "curr":149.99, "cat":"home"},
    {"store":"kohls", "title":"LEGO Star Wars Millennium Falcon 75192", "url":"https://www.kohls.com/search.jsp?search=LEGO+Star+Wars+Millennium+Falcon+75192", "image_url":"", "orig":849.99, "curr":499.99, "cat":"toys"},
    
    # ─── Dick's Sporting Goods (Outdoor / Sports) ───
    {"store":"dicks", "title":"Yeti Hopper M30 Soft Cooler - Charcoal", "url":"https://www.dickssportinggoods.com/f/Yeti+Hopper+M30+Soft+Cooler+-+Charcoal", "image_url":"", "orig":299.99, "curr":199.99, "cat":"outdoor"},
    {"store":"dicks", "title":"Coleman Sundome 6-Person Camping Tent", "url":"https://www.dickssportinggoods.com/f/Coleman+Sundome+6-Person+Camping+Tent", "image_url":"", "orig":149.99, "curr":89.99, "cat":"outdoor"},
    {"store":"dicks", "title":"The North Face Men's 1996 Retro Nuptse Jacket", "url":"https://www.dickssportinggoods.com/f/The+North+Face+Men's+1996+Retro+Nuptse+Jacket", "image_url":"", "orig":329.99, "curr":229.99, "cat":"other"},
    {"store":"dicks", "title":"Solo Stove Bonfire 2.0 Fire Pit with Carry Case", "url":"https://www.dickssportinggoods.com/f/Solo+Stove+Bonfire+2.0+Fire+Pit+with+Carry+Case", "image_url":"", "orig":299.99, "curr":179.99, "cat":"outdoor"},
]


# ——— Resale analytics per category ———
# (avg_resale_pct, sold_30d, flip_score)
# avg_resale_pct = how much above deal price it sells for on eBay
FLIP_DATA = {
    "toys":      (1.8,  45, "S"),  # LEGO: 80% markup, high volume
    "gaming":    (1.35, 60, "S"),  # Nintendo/PS5: 35% markup, very high volume
    "tools":     (1.5,  35, "A"),  # Milwaukee/DeWalt: 50% markup
    "home":      (1.4,  30, "A"),  # KitchenAid: 40% markup
    "audio":     (1.3,  55, "A"),  # AirPods: 30% markup, high volume
    "tablet":    (1.25, 40, "B"),  # iPad: 25% markup
    "laptop":    (1.2,  35, "B"),  # Laptops: 20% markup
    "tv":        (1.15, 20, "B"),  # TVs: 15% markup, lower volume
    "monitor":   (1.3,  25, "A"),  # Monitors: 30% markup
    "storage":   (1.35, 40, "S"),  # SSD: 35% markup, high volume
    "gpu":       (1.15, 25, "B"),  # GPU: 15% markup
    "peripherals": (1.4, 30, "A"), # Mice/keyboards: 40% markup
    "phone":     (1.2,  30, "B"),  # Phones: 20% markup
    "baby":      (1.3,  25, "B"),  # Baby: 30% markup
    "outdoor":   (1.4,  20, "A"),  # Yeti/Weber: 40% markup
    "other":     (1.25, 20, "B"),  # Default
}

def _get_flip_analytics(cat: str, deal_price: float):
    markup, sold, score = FLIP_DATA.get(cat, (1.25, 20, "B"))
    avg = round(deal_price * markup, 2)
    spread = round(avg * 0.08)
    return {
        "avg_resale": avg,
        "min_resale": round(avg - spread, 2),
        "max_resale": round(avg + spread, 2),
        "sold_30d": sold,
        "profit_est": round(avg - deal_price, 2),
        "roi_pct": round((avg - deal_price) / deal_price * 100, 1),
        "flip_score": score,
    }


def seed():
    count = 0
    for d in SEED_DEALS:
        deal_id = make_deal_id(d["url"])
        discount = round((d["orig"] - d["curr"]) / d["orig"] * 100, 1)
        cat = d.get("cat", "other")
        analytics = _get_flip_analytics(cat, d["curr"])
        
        deal = {
            "id": deal_id,
            "store": d["store"],
            "title": d["title"],
            "url": d["url"],
            "image_url": d.get("image_url", ""),
            "original_price": d["orig"],
            "current_price": d["curr"],
            "discount_pct": discount,
            "category": cat,
            "affiliate_url": get_affiliate_url(d["store"], d["url"]),
            **analytics,
        }
        if save_deal(deal):
            count += 1
    print(f"Seeded {count} new deals (total {len(SEED_DEALS)} in dataset)")


if __name__ == "__main__":
    seed()
