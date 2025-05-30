from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import pyodbc
from config import table_name,trendyol_url,sqldatabase,sqlserver


# MSSQL conn
conn = pyodbc.connect(
    "DRIVER={SQL Server};"
    f"SERVER=;{sqlserver}"
    f"DATABASE={sqldatabase};"
    "Trusted_Connection=yes;"
)

cursor = conn.cursor()

# browser settings
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

# ChromeDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# Trendyol link
driver.get(trendyol_url)

# wait to load page
wait = WebDriverWait(driver, 10)
wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

# soup the html
html_icerik = BeautifulSoup(driver.page_source, "html.parser")


class Urun:
    def __init__(self, marka=None, isim=None, fiyat=None, resim_url=None, urun_url=None, etiket=None):
        self.id = etiket
        self.make = marka
        self.name = isim
        self.price = Urun.convert_price(fiyat)
        self.image_url = resim_url
        self.product_url = urun_url

    def __repr__(self):
        return f"Product(id={self.id}, name={self.name}, make={self.make}, price={self.price}, image_url={self.image_url}, product_url={self.product_url})"

    @staticmethod
    def convert_price(price_str):
        """String fiyat bilgisini float'a dönüştür"""
        if price_str is None:
            return 0.0 #if there is no price return 0

        price_str = str(price_str).strip()  # Boşlukları temizle
        price_str = price_str.replace('.', '')  # Binlik ayracını kaldır
        price_str = price_str.replace(',', '.')  # Virgülü ondalık ayracı yap

        try:
            return float(price_str)
        except ValueError:
            return 0.0  # also if there no bug return 0


urun_nesneleri = []
seen_ids = set()
page = 1

while True:
    print(f"\n Sayfa {page} çekiliyor...")
    url = f"{trendyol_url}&pi={page}"
    driver.get(url)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    soup = BeautifulSoup(driver.page_source, "html.parser")

    urun_container = soup.find_all("div", class_="p-card-wrppr with-campaign-view add-to-bs-card")
    if not urun_container:
        print(" Ürün bulunamadı, döngü sonlandırılıyor.")
        break

    yeni_urun_var = False

    for urun in urun_container:
        linkmatch = re.search(r'href="([^"]+)"', str(urun))
        imgmatch = re.search(r'src="(https://cdn\.dsmcdn\.com/[^"]+)"', str(urun))
        namematch = re.search(r'<span class="prdct-desc-cntnr-name[^>]*>(.*?)</span>', str(urun))
        makematch = re.search(r'<span class="prdct-desc-cntnr-ttl"[^>]*>(.*?)</span>', str(urun))
        dispricematch = re.search(r'<div class="price-item lowest-price-discounted">([\d,.]+) TL</div>', str(urun))
        basketpricematch = re.search(r'<div class="price-item basket-price-original">([\d,.]+) TL</div>', str(urun))
        pricematch = re.search(r'<div class="price-item discounted">([\d,.]+) TL</div>', str(urun))
        idmatch = re.search(r'data-id="(\d+)"', str(urun))

        if not idmatch:
            continue

        product_id = idmatch.group(1)
        if product_id in seen_ids:
            continue
        seen_ids.add(product_id)
        yeni_urun_var = True

        product_link = "https://www.trendyol.com" + linkmatch.group(1) if linkmatch else None
        product_make = makematch.group(1) if makematch else None
        product_name = namematch.group(1) if namematch else None

        price_element = (
                urun.find("div", class_="price-item lowest-price-discounted") or
                urun.find("div", class_="price-item basket-price-original") or
                urun.find("div", class_="price-item basket-price-discounted") or
                urun.find("div", class_="price-item discounted")
        )

        product_price = None
        if price_element:
            product_price = price_element.get_text(strip=True).replace("TL", "").strip()

        if not product_price:
            print(f"[FİYAT YOK] ID: {product_id}, İsim: {product_name}")
        product_img = imgmatch.group(1) if imgmatch else None

        urun_nesnesi = Urun(product_make, product_name, product_price, product_img, product_link, product_id)
        urun_nesneleri.append(urun_nesnesi)

    if not yeni_urun_var:
        print("🔁 Yeni ürün kalmadı, döngü durduruluyor.")
        break

    page += 1
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "p-card-wrppr")))

driver.quit()

#importing in to the sql
merge_query = f"""
MERGE INTO dbo.{table_name} AS target
USING (VALUES (?, ?, ?, ?, ?, ?)) AS source (id, make, name, price, img_url, prd_url)
ON target.id = source.id
WHEN MATCHED THEN 
    UPDATE SET 
        target.make = source.make,
        target.name = source.name,
        target.price = source.price,
        target.img_url = source.img_url,
        target.prd_url = source.prd_url
WHEN NOT MATCHED THEN 
    INSERT (id, make, name, price, img_url, prd_url) 
    VALUES (source.id, source.make, source.name, source.price, source.img_url, source.prd_url);
"""

for p in urun_nesneleri:
    cursor.execute(merge_query, (int(p.id), p.make, p.name, p.price, p.image_url, p.product_url))

conn.commit()
cursor.close()
conn.close()
#finale