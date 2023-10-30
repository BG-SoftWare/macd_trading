[ENG](#ENG) || [RUS](#RUS)

# ENG
<h1 align=center>MACD Trading</h1>

This project is a program to automate trading on the cryptocurrency exchange using the MACD indicator.

<h2 align=center>Contents</h2>

1. [Features](#Features)
2. [Technologies](#Technologies)
3. [Preparing to work](#Preparing-to-work)
4. [Usage](#Usage)
5. [DISCLAIMER](#DISCLAIMER)

## Features
The main features of this application include:
  + complete autonomy (the user only needs to make initial settings and run the program)
  + speed of operation (high speed of data processing was obtained due to the use of Redis -- NoSQL database)
  + easy adaptation to other exchanges (in this example, Binance is used, but a similar mechanism can be implemented on other exchanges)
  + possibility to add analysis of other indicators

## Technologies

| Technology | Description |
| ----------- | ----------- |
| Python    | Programming language in which the project is implemented   |
| MySQL    | Relational database for storing transaction history   |
| Redis    | Non-relational database  |
| SQLAlchemy    | SQL toolkit and Object Relational Mapper that gives application developers the full power and flexibility of SQL   |
| Binance SDK    | This is a lightweight library that works as a connector to Binance public API   |
| requests    | An elegant and simple HTTP library for Python   |
| numpy    | The fundamental package for scientific computing with Python   |
| pandas    | Flexible and easy to use open source data analysis and manipulation tool   |
| click    | A Python package for creating command line interfaces  |

## Preparing to work
1. Install [Python](https://www.python.org/downloads/)
2. Download the source code of the project
3. Deploy the virtual environment (venv) in the project folder. To do this, open a terminal in the project folder and enter the command:  
   `python3 -m venv venv`
4. Activate the virtual environment with the command  
   `source venv/bin/activate`
5. Install the project dependencies, which are located in the requirements.txt file. To do this, enter the command in the terminal:  
   `pip install -r requirements.txt`
6. Change the values in the file `configs/config.ini`
7. Change the values in the file `configs/macd_config.json`
8. Change the values in the file `.env.example` , which is in the folder _configs_ and rename it to `.env`

## Usage
1. To run the program you need to write the command in the command line:
   `python3 trading.py $TICKER`,
   where _$TICKER_ -- the name of the pair you want to trade (must match one of the keys of the file `configs/macd_config.json`).

## DISCLAIMER
The user of this software acknowledges that it is provided "as is" without any express or implied warranties. 
The software developer is not liable for any direct or indirect financial losses resulting from the use of this software. 
The user is solely responsible for his/her actions and decisions related to the use of the software.

---

# RUS
<h1 align=center>MACD Trading</h1>

Этот проект представляет собой программу для автоматизации торговли на криптовалютной бирже при помощи индикатора MACD.

<h2 align=center>Содержание</h2>

1. [Особенности](#Особенности)
2. [Технологии](#Технологии)
3. [Подготовка к работе](#Подготовка-к-работе)
4. [Использование](#Использование)
5. [ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ](#ОТКАЗ-ОТ-ОТВЕТСТВЕННОСТИ)

## Особенности
Основные особенности этого приложения включают в себя:
  + полная автономность (пользователю необходимо лишь сделать начальные настройки и запустить программу)
  + скорость работы (высокая скорость обработки данных была получена за счет использования Redis -- NoSQL базы данных)
  + простота адаптации под другие биржи (в этом примере используется биржа Binance, однако подобный механизм можно реализовать на других биржах)
  + возможность добавить анализ других индикаторов

## Технологии

| Технология / Библиотека | Описание |
| ----------- | ----------- |
| Python    | Язык программирования, на котором реализован проект   |
| MySQL    | Реляционная база данных для хранения истории сделок   |
| Redis    | Нереляционная база данных  |
| SQLAlchemy    | Комплексный набор инструментов для работы с реляционными базами данных в Python   |
| Binance SDK    | Официальный SDK для взаимодействия с биржей Binance   |
| requests    | HTTP-библиотека для Python. Используется для отправки HTTP-запросов и получения ответов   |
| numpy    | Пакет для научных вычислений на Python   |
| pandas    | Инструмент для анализа и обработки данных   |
| click    | Парсер аргументов командной строки   |

## Подготовка к работе
1. Установите [Python](https://www.python.org/downloads/)
2. Скачайте исходный код проекта
3. Разверните виртуальное окружение (venv) в папке с проектом. Для этого откройте терминал в папке с проектом и введите команду:  
   `python3 -m venv venv`
4. Активируйте виртуальное окружение командой  
   `source venv/bin/activate`
5. Установите зависимости проекта, которые находятся в файле requirements.txt. Для этого в терминале введите команду:  
   `pip install -r requirements.txt`
6. Измените значения в файле `configs/config.ini`
7. Измените значения в файле `configs/macd_config.json`
8. Внесите изменения в файл `.env.example` , который находится в папке _configs_ и переименуйте его в `.env`

## Использование
1. Для запуска программы Вам необходимо в командной строке прописать команду:
   `python3 trading.py $TICKER`,
   где _$TICKER_ -- название актива, которым Вы хотите торговать (должен соответствовать одному из ключей файла `configs/macd_config.json`).

## ОТКАЗ ОТ ОТВЕТСТВЕННОСТИ
Пользователь этого программного обеспечения подтверждает, что оно предоставляется "как есть", без каких-либо явных или неявных гарантий. 
Разработчик программного обеспечения не несет ответственности за любые прямые или косвенные финансовые потери, возникшие в результате использования данного программного обеспечения. 
Пользователь несет полную ответственность за свои действия и решения, связанные с использованием программного обеспечения.
