import requests
from bs4 import BeautifulSoup
import json
import os
import logging
import time
import openpyxl

logger = logging.getLogger("parser_loger")
logger.setLevel(logging.INFO)
console_headler = logging.StreamHandler()
formatter = logging.Formatter('[%(levelname)s] %(asctime)s %(lineno)d : %(message)s')
console_headler.setFormatter(formatter)

logger.addHandler(console_headler)


MAIN_URL = 'https://novosibirsk.leroymerlin.ru/catalogue/sad/'
PAGE_URL = 'https://novosibirsk.leroymerlin.ru/content/elbrus/novosibirsk/ru/catalogue/sad/{}/_jcr_content/universe-list/universe_list.model.json?page={}'


def save_page(response: str, file='page.html'):
    with open(file, 'w', encoding='utf8') as html_file:
        html_file.write(response)


def load_page(file: str):
    with open(file, 'r', encoding='utf8') as html_file:
        return html_file.read()


def write_json(data, file='data.json'):
    with open(file, 'w', encoding='utf8') as json_file:
        json.dump(data, json_file, ensure_ascii=False, indent=4)


def load_json(file='categories.json'):
    with open(file, 'r', encoding='utf8') as json_file:
        return json.load(json_file)


def create_catalogs_directory(file='categories.json'):
    with open(file, 'r', encoding='utf8') as json_file:
        categories = json.load(json_file)
    for categorie in categories:
        os.makedirs(categorie['href'][1:-1])


def get_categories(json_file='categories.json') -> list:
    if os.path.isfile(json_file):
        return load_json(json_file)
    response = requests.get(MAIN_URL)
    soup = BeautifulSoup(response.text, 'lxml')
    categories_blocks = soup.select('uc-catalog-facet-link')
    categories = []
    for categorie_block in categories_blocks:
        name_categorie = categorie_block.select_one('a').text.replace('\n', '').strip()
        href_categorie = categorie_block.select_one('a')['href']
        categories.append({'name': name_categorie, 'href': href_categorie})
    write_json(categories, json_file)
    return categories


def get_max_page_in_catalog(category: dict) -> int:
    page_data = get_page_data(category, 1)
    return int(page_data['totalPages'])


def get_page_data(category:dict, page:int) -> dict:
    categorie_key = category['href'][1: -1].split('/')[-1]
    path_page = category['href'][1:] + '{}'.format(page)
    path_json = path_page + '/{}.json'.format(page)
    if os.path.isfile(path_json):
        page_data = load_json(path_json)
    else:
        if not os.path.exists(path_page):
            os.makedirs(path_page)
        url = PAGE_URL.format(categorie_key, 1)
        response = requests.get(url)
        page_data = response.json()
        write_json(response.json(), path_json)
    return page_data


def get_products(category: dict, page: int, count_product: int):
    page_data = get_page_data(category, page)
    products = page_data['productList']
    path_page = category['href'][1:] + '{}'.format(page)
    data_products_paths = []
    for product in products:
        start_time = time.time()
        count_product -= 1
        article = product['article']
        data_product_path = path_page + '/{}.json'.format(article)
        data_products_paths.append(data_product_path)
        if os.path.isfile(data_product_path):
            continue
        url = product['url']
        response = requests.get(url)
        html = response.text
        name = product['displayedName']
        price = product['price']
        images = [img['link'] for img in product['productImages']]
        description, characteristick = get_additional_data(html)
        data_product = {'category': category['name'],
                        'article': article,
                        'name': name,
                        'price': price,
                        'images': images,
                        'description': description,
                        'characteristick': characteristick}
        data_product_path = path_page + '/{}.json'.format(article)
        write_json(data_product, data_product_path)
        time_per_cicle = time.time() - start_time

        logger.info("Осталось {} продуктов и примерно {} минут".format(count_product, count_product*time_per_cicle/60))
    return data_products_paths


def get_additional_data(html: str):
    soup = BeautifulSoup(html, 'lxml')
    description_block = soup.select_one('.pdp-section.pdp-section--product-description')
    if description_block:
        description = description_block.select_one('uc-pdp-section-vlimited.section__vlimit').text
        description = description.replace('\n\n', '')
    else:
        description = str()
    characteristick_block = soup.select_one('.pdp-section.pdp-section--product-characteristicks')
    if characteristick_block:
        characteristick = characteristick_block.select_one('uc-pdp-section-vlimited.section__vlimit').text
        characteristick = characteristick.split('\n                \n            ')
        characteristick = [char.split('\n\n                ') for char in characteristick]
        characteristick = [' - '.join([char[0].replace('\n\n\n', ''), char[1]]) for char in characteristick if len(char)== 2]
        characteristick = '\n'.join(characteristick)
    else:
        characteristick = str()
    return description, characteristick


def get_count_products(category: dict, page: int):
    page_data = get_page_data(category, page)
    return len(page_data['productList'])


if __name__ == '__main__':
    logger.info('Получение категорий')
    categories = get_categories()
    logger.info('Категории получены')
    logger.info('Получение количества продуктов')
    count_product = 0
    for category in categories:
        max_page = get_max_page_in_catalog(category)
        for page in range(1, max_page+1):
            count_product_on_page = get_count_products(category, page)
            count_product += count_product_on_page
            logger.info('Количество продуктов: "{}"'.format(count_product))
    products_paths = []
    for category in categories:
        max_page = get_max_page_in_catalog(category)
        for page in range(1, max_page + 1):
            products = get_products(category, page, count_product)
            products_paths.extend(products)
            count_product -= len(products)
