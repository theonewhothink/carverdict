#!/usr/bin/env python3
"""build_events.py — the motoring calendar: every event worth travelling for.

Two layers, deliberately:

  1. A curated spine of ~130 events that recur every year. Names, venues, countries,
     categories, official sites and the month they land in are stable facts, so they are
     committed rather than scraped. This guarantees the section exists even if every
     network call fails on a build.

  2. A live enrichment pass against Wikipedia (MediaWiki API, batched 20 titles per
     request) that pulls the current article intro and, where the article states it,
     the confirmed date of the next edition. Dates move — the 2027 Formula 1 calendar
     was still provisional in mid-2026 — so a hardcoded date table would be wrong within
     months. Confirmed dates are labelled as confirmed; everything else is shown as the
     window the event normally occupies, which is the honest answer.

Output:
  /events/                 searchable, filterable index (category, country, month)
  /events/<slug>/          one page per event, with Event JSON-LD when a date is known
  /assets/events.json      the same data as a feed
"""
import html, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
CACHE = ROOT / "data" / "events_cache.json"
ORIGIN = os.environ.get("SITE_ORIGIN", "https://carsite.adir-073.workers.dev").rstrip("/")
BRAND = "CarVerdict"
UA = "CarVerdict/1.0 (https://carsite.adir-073.workers.dev) python-urllib"
TODAY = date.today()

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]

# name, category, series, country, city/venue, month, typical window, official site, wikipedia title
E = [
    # ---------------------------------------------------------------- Formula 1
    ("Monaco Grand Prix", "Formula 1", "FIA Formula One World Championship", "Monaco", "Circuit de Monaco, Monte Carlo", 5, "late May", "https://www.acm.mc/", "Monaco Grand Prix"),
    ("British Grand Prix", "Formula 1", "FIA Formula One World Championship", "United Kingdom", "Silverstone Circuit", 7, "early July", "https://www.silverstone.co.uk/", "British Grand Prix"),
    ("Italian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Italy", "Autodromo Nazionale Monza", 9, "early September", "https://www.monzanet.it/", "Italian Grand Prix"),
    ("Belgian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Belgium", "Circuit de Spa-Francorchamps", 7, "late July", "https://www.spa-francorchamps.be/", "Belgian Grand Prix"),
    ("Japanese Grand Prix", "Formula 1", "FIA Formula One World Championship", "Japan", "Suzuka International Racing Course", 4, "late March or April", "https://www.suzukacircuit.jp/", "Japanese Grand Prix"),
    ("United States Grand Prix", "Formula 1", "FIA Formula One World Championship", "United States", "Circuit of the Americas, Austin", 10, "October", "https://circuitoftheamericas.com/", "United States Grand Prix"),
    ("Las Vegas Grand Prix", "Formula 1", "FIA Formula One World Championship", "United States", "Las Vegas Strip Circuit", 11, "November", "https://www.f1lasvegasgp.com/", "Las Vegas Grand Prix"),
    ("Miami Grand Prix", "Formula 1", "FIA Formula One World Championship", "United States", "Miami International Autodrome", 5, "early May", "https://f1miamigp.com/", "Miami Grand Prix"),
    ("Singapore Grand Prix", "Formula 1", "FIA Formula One World Championship", "Singapore", "Marina Bay Street Circuit", 9, "September, run at night", "https://www.singaporegp.sg/", "Singapore Grand Prix"),
    ("Australian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Australia", "Albert Park, Melbourne", 3, "March", "https://www.grandprix.com.au/", "Australian Grand Prix"),
    ("São Paulo Grand Prix", "Formula 1", "FIA Formula One World Championship", "Brazil", "Autódromo José Carlos Pace, Interlagos", 11, "November", "https://www.formula1.com/", "São Paulo Grand Prix"),
    ("Canadian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Canada", "Circuit Gilles Villeneuve, Montreal", 6, "June", "https://www.gpcanada.ca/", "Canadian Grand Prix"),
    ("Hungarian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Hungary", "Hungaroring, Mogyoród", 7, "late July", "https://hungaroring.hu/", "Hungarian Grand Prix"),
    ("Austrian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Austria", "Red Bull Ring, Spielberg", 6, "late June or early July", "https://projekt-spielberg.com/", "Austrian Grand Prix"),
    ("Emilia Romagna Grand Prix", "Formula 1", "FIA Formula One World Championship", "Italy", "Autodromo Enzo e Dino Ferrari, Imola", 5, "May", "https://www.autodromoimola.it/", "Emilia-Romagna Grand Prix"),
    ("Mexico City Grand Prix", "Formula 1", "FIA Formula One World Championship", "Mexico", "Autódromo Hermanos Rodríguez", 10, "late October", "https://mexicogp.mx/", "Mexico City Grand Prix"),
    ("Abu Dhabi Grand Prix", "Formula 1", "FIA Formula One World Championship", "United Arab Emirates", "Yas Marina Circuit", 12, "early December, season finale", "https://www.yasmarinacircuit.com/", "Abu Dhabi Grand Prix"),
    ("Bahrain Grand Prix", "Formula 1", "FIA Formula One World Championship", "Bahrain", "Bahrain International Circuit, Sakhir", 3, "March, often the season opener", "https://www.bahraingp.com/", "Bahrain Grand Prix"),
    ("Saudi Arabian Grand Prix", "Formula 1", "FIA Formula One World Championship", "Saudi Arabia", "Jeddah Corniche Circuit", 3, "March or April", "https://www.saudiarabiangp.com/", "Saudi Arabian Grand Prix"),
    ("Azerbaijan Grand Prix", "Formula 1", "FIA Formula One World Championship", "Azerbaijan", "Baku City Circuit", 9, "September", "https://www.bakucitycircuit.com/", "Azerbaijan Grand Prix"),
    ("Chinese Grand Prix", "Formula 1", "FIA Formula One World Championship", "China", "Shanghai International Circuit", 4, "March or April", "https://www.formula1.com/", "Chinese Grand Prix"),
    ("Qatar Grand Prix", "Formula 1", "FIA Formula One World Championship", "Qatar", "Lusail International Circuit", 11, "late November", "https://www.formula1.com/", "Qatar Grand Prix"),
    ("Spanish Grand Prix", "Formula 1", "FIA Formula One World Championship", "Spain", "Madrid and Circuit de Barcelona-Catalunya", 9, "September", "https://www.formula1.com/", "Spanish Grand Prix"),
    ("Formula 1 pre-season testing", "Formula 1", "FIA Formula One World Championship", "Bahrain", "Bahrain International Circuit, Sakhir", 2, "late February", "https://www.formula1.com/", "Formula One testing"),

    # ---------------------------------------------------------------- Endurance
    ("24 Hours of Le Mans", "Endurance", "FIA World Endurance Championship", "France", "Circuit de la Sarthe, Le Mans", 6, "the second weekend of June", "https://www.24h-lemans.com/", "24 Hours of Le Mans"),
    ("Rolex 24 at Daytona", "Endurance", "IMSA SportsCar Championship", "United States", "Daytona International Speedway", 1, "late January", "https://www.daytonainternationalspeedway.com/", "24 Hours of Daytona"),
    ("12 Hours of Sebring", "Endurance", "IMSA SportsCar Championship", "United States", "Sebring International Raceway", 3, "mid-March", "https://www.sebringraceway.com/", "12 Hours of Sebring"),
    ("Nürburgring 24 Hours", "Endurance", "Nürburgring Langstrecken-Serie", "Germany", "Nürburgring Nordschleife", 5, "late May or June", "https://www.24h-rennen.de/", "24 Hours of Nürburgring"),
    ("Spa 24 Hours", "Endurance", "GT World Challenge Europe", "Belgium", "Circuit de Spa-Francorchamps", 6, "late June or July", "https://www.spa-francorchamps.be/", "24 Hours of Spa"),
    ("Bathurst 12 Hour", "Endurance", "Intercontinental GT Challenge", "Australia", "Mount Panorama Circuit, Bathurst", 2, "February", "https://www.bathurst12hour.com.au/", "Bathurst 12 Hour"),
    ("Petit Le Mans", "Endurance", "IMSA SportsCar Championship", "United States", "Road Atlanta, Braselton", 10, "October", "https://www.imsa.com/", "Petit Le Mans"),
    ("6 Hours of Spa-Francorchamps", "Endurance", "FIA World Endurance Championship", "Belgium", "Circuit de Spa-Francorchamps", 5, "May", "https://www.fiawec.com/", "6 Hours of Spa-Francorchamps"),
    ("6 Hours of Fuji", "Endurance", "FIA World Endurance Championship", "Japan", "Fuji Speedway", 9, "September", "https://www.fiawec.com/", "6 Hours of Fuji"),
    ("8 Hours of Bahrain", "Endurance", "FIA World Endurance Championship", "Bahrain", "Bahrain International Circuit", 11, "November, WEC finale", "https://www.fiawec.com/", "Bapco 8 Hours of Bahrain"),
    ("6 Hours of Imola", "Endurance", "FIA World Endurance Championship", "Italy", "Autodromo Enzo e Dino Ferrari, Imola", 4, "April", "https://www.fiawec.com/", "6 Hours of Imola"),
    ("6 Hours of São Paulo", "Endurance", "FIA World Endurance Championship", "Brazil", "Autódromo José Carlos Pace, Interlagos", 7, "July", "https://www.fiawec.com/", "6 Hours of São Paulo"),
    ("Qatar 1812 km", "Endurance", "FIA World Endurance Championship", "Qatar", "Lusail International Circuit", 2, "late February, WEC opener", "https://www.fiawec.com/", "Qatar 1812 km"),
    ("Suzuka 8 Hours", "Endurance", "FIM Endurance World Championship", "Japan", "Suzuka International Racing Course", 8, "late July or August", "https://www.suzukacircuit.jp/", "Suzuka 8 Hours"),
    ("Bathurst 1000", "Touring car", "Repco Supercars Championship", "Australia", "Mount Panorama Circuit, Bathurst", 10, "October", "https://www.supercars.com/", "Bathurst 1000"),

    # ---------------------------------------------------------------- Oval and stock car
    ("Indianapolis 500", "IndyCar", "NTT IndyCar Series", "United States", "Indianapolis Motor Speedway", 5, "the Sunday of Memorial Day weekend", "https://www.indianapolismotorspeedway.com/", "Indianapolis 500"),
    ("Daytona 500", "NASCAR", "NASCAR Cup Series", "United States", "Daytona International Speedway", 2, "mid-February, the season opener", "https://www.daytonainternationalspeedway.com/", "Daytona 500"),
    ("Coca-Cola 600", "NASCAR", "NASCAR Cup Series", "United States", "Charlotte Motor Speedway", 5, "Memorial Day weekend", "https://www.charlottemotorspeedway.com/", "Coca-Cola 600"),
    ("Brickyard 400", "NASCAR", "NASCAR Cup Series", "United States", "Indianapolis Motor Speedway", 7, "July", "https://www.indianapolismotorspeedway.com/", "Brickyard 400"),
    ("Southern 500", "NASCAR", "NASCAR Cup Series", "United States", "Darlington Raceway", 8, "Labor Day weekend", "https://www.darlingtonraceway.com/", "Southern 500"),
    ("Long Beach Grand Prix", "IndyCar", "NTT IndyCar Series", "United States", "Streets of Long Beach, California", 4, "April", "https://www.gplb.com/", "Grand Prix of Long Beach"),
    ("Indianapolis Motor Speedway road course double", "IndyCar", "NTT IndyCar Series", "United States", "Indianapolis Motor Speedway road course", 5, "May, the weekend before the 500", "https://www.indianapolismotorspeedway.com/", "Grand Prix of Indianapolis"),

    # ---------------------------------------------------------------- Motorcycles
    ("Isle of Man TT", "Motorcycle", "Isle of Man TT Races", "Isle of Man", "Snaefell Mountain Course", 6, "late May into June", "https://www.iomtt.com/", "Isle of Man TT"),
    ("Dutch TT Assen", "MotoGP", "MotoGP World Championship", "Netherlands", "TT Circuit Assen", 6, "late June", "https://www.ttcircuit.com/", "Dutch TT"),
    ("Italian Grand Prix Mugello", "MotoGP", "MotoGP World Championship", "Italy", "Mugello Circuit", 6, "June", "https://www.motogp.com/", "Italian motorcycle Grand Prix"),
    ("Spanish Grand Prix Jerez", "MotoGP", "MotoGP World Championship", "Spain", "Circuito de Jerez", 4, "late April", "https://www.motogp.com/", "Spanish motorcycle Grand Prix"),
    ("Grand Prix of the Americas", "MotoGP", "MotoGP World Championship", "United States", "Circuit of the Americas, Austin", 4, "April", "https://www.motogp.com/", "Grand Prix of the Americas"),
    ("German Grand Prix Sachsenring", "MotoGP", "MotoGP World Championship", "Germany", "Sachsenring", 7, "July", "https://www.motogp.com/", "German motorcycle Grand Prix"),
    ("San Marino Grand Prix", "MotoGP", "MotoGP World Championship", "San Marino", "Misano World Circuit Marco Simoncelli", 9, "September", "https://www.motogp.com/", "San Marino and Rimini's Riviera motorcycle Grand Prix"),
    ("Japanese Grand Prix Motegi", "MotoGP", "MotoGP World Championship", "Japan", "Mobility Resort Motegi", 9, "September or October", "https://www.motogp.com/", "Japanese motorcycle Grand Prix"),
    ("Australian Grand Prix Phillip Island", "MotoGP", "MotoGP World Championship", "Australia", "Phillip Island Grand Prix Circuit", 10, "October", "https://www.motogp.com/", "Australian motorcycle Grand Prix"),
    ("Malaysian Grand Prix Sepang", "MotoGP", "MotoGP World Championship", "Malaysia", "Sepang International Circuit", 11, "November", "https://www.motogp.com/", "Malaysian motorcycle Grand Prix"),
    ("Valencia Grand Prix", "MotoGP", "MotoGP World Championship", "Spain", "Circuit Ricardo Tormo, Valencia", 11, "November, season finale", "https://www.motogp.com/", "Valencian Community motorcycle Grand Prix"),
    ("Sturgis Motorcycle Rally", "Gathering", "Independent", "United States", "Sturgis, South Dakota", 8, "the first full week of August", "https://www.sturgismotorcyclerally.com/", "Sturgis Motorcycle Rally"),
    ("Daytona Bike Week", "Gathering", "Independent", "United States", "Daytona Beach, Florida", 3, "early March", "https://www.officialbikeweek.com/", "Daytona Beach Bike Week"),

    # ---------------------------------------------------------------- Rally and rally raid
    ("Rallye Monte-Carlo", "Rally", "FIA World Rally Championship", "Monaco", "Monaco and the French Alps", 1, "late January, the WRC opener", "https://www.wrc.com/", "Monte Carlo Rally"),
    ("Rally Sweden", "Rally", "FIA World Rally Championship", "Sweden", "Umeå, Västerbotten", 2, "February, the only full-winter round", "https://www.wrc.com/", "Rally Sweden"),
    ("Safari Rally Kenya", "Rally", "FIA World Rally Championship", "Kenya", "Naivasha and the Rift Valley", 3, "March", "https://www.wrc.com/", "Safari Rally"),
    ("Rally de Portugal", "Rally", "FIA World Rally Championship", "Portugal", "Matosinhos and the north", 5, "May", "https://www.wrc.com/", "Rally de Portugal"),
    ("Rally Italia Sardegna", "Rally", "FIA World Rally Championship", "Italy", "Alghero, Sardinia", 6, "June", "https://www.wrc.com/", "Rally d'Italia Sardegna"),
    ("Secto Rally Finland", "Rally", "FIA World Rally Championship", "Finland", "Jyväskylä", 8, "August", "https://www.wrc.com/", "Rally Finland"),
    ("Acropolis Rally Greece", "Rally", "FIA World Rally Championship", "Greece", "Lamia and central Greece", 9, "September", "https://www.wrc.com/", "Acropolis Rally"),
    ("Central European Rally", "Rally", "FIA World Rally Championship", "Germany", "Bavaria, Czechia and Austria", 10, "October", "https://www.wrc.com/", "Central European Rally"),
    ("Rally Japan", "Rally", "FIA World Rally Championship", "Japan", "Aichi and Gifu prefectures", 11, "November, the WRC finale", "https://www.wrc.com/", "Rally Japan"),
    ("Dakar Rally", "Rally", "FIA and FIM Cross-Country World Rally Championship", "Saudi Arabia", "Saudi Arabia, two weeks of desert stages", 1, "the first two weeks of January", "https://www.dakar.com/", "Dakar Rally"),
    ("Baja 1000", "Rally", "SCORE International", "Mexico", "Baja California peninsula", 11, "November", "https://score-international.com/", "Baja 1000"),

    # ---------------------------------------------------------------- Electric and single seater
    ("Monaco E-Prix", "Formula E", "FIA Formula E World Championship", "Monaco", "Circuit de Monaco", 5, "May", "https://www.fiaformulae.com/", "Monaco ePrix"),
    ("London E-Prix", "Formula E", "FIA Formula E World Championship", "United Kingdom", "ExCeL London", 7, "July, the season finale", "https://www.fiaformulae.com/", "London ePrix"),
    ("Tokyo E-Prix", "Formula E", "FIA Formula E World Championship", "Japan", "Tokyo Street Circuit, Odaiba", 5, "May", "https://www.fiaformulae.com/", "Tokyo ePrix"),
    ("Berlin E-Prix", "Formula E", "FIA Formula E World Championship", "Germany", "Tempelhof Airport Street Circuit", 5, "May", "https://www.fiaformulae.com/", "Berlin ePrix"),
    ("São Paulo E-Prix", "Formula E", "FIA Formula E World Championship", "Brazil", "Anhembi Sambadrome", 12, "December", "https://www.fiaformulae.com/", "São Paulo ePrix"),
    ("Macau Grand Prix", "Single seater", "Macau Grand Prix", "Macau", "Guia Circuit", 11, "mid-November", "https://www.macau.grandprix.gov.mo/", "Macau Grand Prix"),
    ("Formula 2 season", "Single seater", "FIA Formula 2 Championship", "International", "Supporting the Formula 1 calendar", 3, "March to December, alongside Formula 1", "https://www.fiaformula2.com/", "FIA Formula 2 Championship"),
    ("Formula 3 season", "Single seater", "FIA Formula 3 Championship", "International", "Supporting the Formula 1 calendar", 3, "March to September, alongside Formula 1", "https://www.fiaformula3.com/", "FIA Formula 3 Championship"),
    ("F1 Academy season", "Single seater", "F1 Academy", "International", "Supporting the Formula 1 calendar", 4, "spring to autumn, alongside Formula 1", "https://www.f1academy.com/", "F1 Academy"),
    ("Super Formula season", "Single seater", "Super Formula Championship", "Japan", "Japanese circuits including Suzuka and Fuji", 3, "March to October", "https://superformula.net/", "Super Formula Championship"),
    ("Super GT season", "Sports car", "Super GT", "Japan", "Japanese circuits including Fuji and Suzuka", 4, "April to November", "https://supergt.net/", "Super GT"),

    # ---------------------------------------------------------------- Hillclimb and speed
    ("Pikes Peak International Hill Climb", "Hillclimb", "Pikes Peak International Hill Climb", "United States", "Pikes Peak Highway, Colorado", 6, "late June", "https://ppihc.org/", "Pikes Peak International Hill Climb"),
    ("Bonneville Speed Week", "Hillclimb", "Southern California Timing Association", "United States", "Bonneville Salt Flats, Utah", 8, "August", "https://scta-bni.org/", "Bonneville Speedway"),
    ("Race of Champions", "Gathering", "Race of Champions", "International", "Location changes every year", 1, "January or February", "https://www.raceofchampions.com/", "Race of Champions"),

    # ---------------------------------------------------------------- Historic racing and festivals
    ("Goodwood Festival of Speed", "Historic", "Goodwood", "United Kingdom", "Goodwood House, West Sussex", 7, "mid-July", "https://www.goodwood.com/motorsport/festival-of-speed/", "Goodwood Festival of Speed"),
    ("Goodwood Revival", "Historic", "Goodwood", "United Kingdom", "Goodwood Motor Circuit, West Sussex", 9, "September", "https://www.goodwood.com/motorsport/goodwood-revival/", "Goodwood Revival"),
    ("Goodwood Members' Meeting", "Historic", "Goodwood", "United Kingdom", "Goodwood Motor Circuit, West Sussex", 4, "April", "https://www.goodwood.com/motorsport/members-meeting/", "Goodwood Members' Meeting"),
    ("Mille Miglia", "Historic", "1000 Miglia", "Italy", "Brescia to Rome and back", 6, "June", "https://1000miglia.it/", "Mille Miglia"),
    ("Le Mans Classic", "Historic", "Peter Auto", "France", "Circuit de la Sarthe, Le Mans", 7, "July, in odd-numbered years", "https://www.lemansclassic.com/", "Le Mans Classic"),
    ("Monaco Historic Grand Prix", "Historic", "Automobile Club de Monaco", "Monaco", "Circuit de Monaco", 5, "May, in even-numbered years", "https://www.acm.mc/", "Monaco Historic Grand Prix"),
    ("Silverstone Festival", "Historic", "Silverstone", "United Kingdom", "Silverstone Circuit", 8, "late August", "https://www.silverstone.co.uk/", "Silverstone Classic"),
    ("Classic Le Mans support paddock", "Historic", "Automobile Club de l'Ouest", "France", "Circuit de la Sarthe, Le Mans", 6, "June, race week", "https://www.24h-lemans.com/", "24 Hours of Le Mans"),
    ("Tour Auto Optic 2000", "Historic", "Peter Auto", "France", "Paris to a different finish town each year", 4, "April or May", "https://www.peterauto.peter.fr/", "Tour Auto"),
    ("Rallye Monte-Carlo Historique", "Historic", "Automobile Club de Monaco", "Monaco", "Monaco and the Alps", 1, "late January or February", "https://www.acm.mc/", "Monte Carlo Rally"),
    ("Bicester Heritage Scramble", "Gathering", "Bicester Motion", "United Kingdom", "Bicester Heritage, Oxfordshire", 4, "several times a year", "https://bicestermotion.com/", "Bicester Heritage"),
    ("Rennsport Reunion", "Gathering", "Porsche Cars North America", "United States", "Laguna Seca, California", 9, "held every few years", "https://www.porsche.com/", "Rennsport Reunion"),

    # ---------------------------------------------------------------- Concours
    ("Pebble Beach Concours d'Elegance", "Concours", "Monterey Car Week", "United States", "Pebble Beach, California", 8, "the third Sunday in August", "https://www.pebblebeachconcours.net/", "Pebble Beach Concours d'Elegance"),
    ("Monterey Car Week", "Concours", "Monterey Car Week", "United States", "Monterey Peninsula, California", 8, "the week around the third Sunday in August", "https://montereycarweek.com/", "Monterey Car Week"),
    ("The Quail, A Motorsports Gathering", "Concours", "Monterey Car Week", "United States", "Quail Lodge, Carmel, California", 8, "August, during Monterey Car Week", "https://www.quaillodge.com/", "The Quail, A Motorsports Gathering"),
    ("Concorso d'Eleganza Villa d'Este", "Concours", "BMW Group Classic", "Italy", "Villa d'Este, Lake Como", 5, "May", "https://concorsodeleganzavilladeste.com/", "Concorso d'Eleganza Villa d'Este"),
    ("The Amelia", "Concours", "Hagerty", "United States", "Amelia Island, Florida", 3, "late February or March", "https://www.theamelia.com/", "Amelia Island Concours d'Elegance"),
    ("Salon Privé", "Concours", "Salon Privé", "United Kingdom", "Blenheim Palace, Oxfordshire", 8, "late August or September", "https://www.salonpriveconcours.com/", "Salon Privé"),
    ("Concours of Elegance", "Concours", "Concours of Elegance", "United Kingdom", "Hampton Court Palace, London", 9, "early September", "https://concoursofelegance.co.uk/", "Concours of Elegance"),
    ("London Concours", "Concours", "London Concours", "United Kingdom", "Honourable Artillery Company, London", 6, "June", "https://londonconcours.co.uk/", "London Concours"),
    ("Greenwich Concours d'Elegance", "Concours", "Hagerty", "United States", "Roger Sherman Baldwin Park, Connecticut", 6, "late May or June", "https://greenwichconcours.com/", "Greenwich Concours d'Elegance"),
    ("Cavallino Classic", "Concours", "Cavallino", "United States", "Palm Beach, Florida", 1, "January", "https://cavallino.com/", "Cavallino Classic"),
    ("Zoute Grand Prix", "Concours", "Zoute Events", "Belgium", "Knokke-Heist, Flanders", 10, "October", "https://www.zoutegrandprix.be/", "Zoute Grand Prix"),
    ("Audrain Newport Concours", "Concours", "Audrain Automobile Museum", "United States", "Newport, Rhode Island", 10, "late September or October", "https://audrainconcours.com/", "Audrain Automobile Museum"),
    ("Concours d'Elegance of America", "Concours", "Concours d'Elegance of America", "United States", "Plymouth, Michigan", 7, "July", "https://www.concoursusa.org/", "Concours d'Elegance of America"),

    # ---------------------------------------------------------------- Auctions
    ("Monterey collector car auctions", "Auction", "RM Sotheby's, Gooding, Bonhams, Mecum", "United States", "Monterey Peninsula, California", 8, "August, during Monterey Car Week", "https://rmsothebys.com/", "Monterey Car Week"),
    ("Scottsdale auction week", "Auction", "Barrett-Jackson, RM Sotheby's, Bonhams", "United States", "Scottsdale, Arizona", 1, "January", "https://www.barrett-jackson.com/", "Barrett-Jackson"),
    ("Mecum Kissimmee", "Auction", "Mecum Auctions", "United States", "Osceola Heritage Park, Kissimmee, Florida", 1, "January, the largest collector car auction in the world", "https://www.mecum.com/", "Mecum Auctions"),
    ("Rétromobile Paris auctions", "Auction", "Artcurial and Bonhams", "France", "Paris Expo Porte de Versailles", 2, "February, during Rétromobile", "https://www.artcurial.com/", "Rétromobile"),
    ("Amelia Island auctions", "Auction", "Gooding and Bonhams", "United States", "Amelia Island, Florida", 3, "March, during The Amelia", "https://www.goodingco.com/", "Amelia Island Concours d'Elegance"),
    ("Bonhams Goodwood Revival Sale", "Auction", "Bonhams", "United Kingdom", "Goodwood Motor Circuit, West Sussex", 9, "September, during the Revival", "https://cars.bonhams.com/", "Bonhams"),

    # ---------------------------------------------------------------- Motor shows
    ("IAA Mobility", "Motor show", "VDA", "Germany", "Messe München and Munich city centre", 9, "September, in odd-numbered years", "https://www.iaa-mobility.com/", "IAA Mobility"),
    ("Japan Mobility Show", "Motor show", "JAMA", "Japan", "Tokyo Big Sight", 10, "October and November, in odd-numbered years", "https://www.japan-mobility-show.com/", "Tokyo Motor Show"),
    ("Auto Shanghai", "Motor show", "CAAM", "China", "National Exhibition and Convention Center, Shanghai", 4, "April, in odd-numbered years", "https://www.autoshanghai.org/", "Auto Shanghai"),
    ("Auto China Beijing", "Motor show", "CAAM", "China", "China International Exhibition Center, Beijing", 4, "April, in even-numbered years", "https://www.autochina-show.com/", "Beijing International Automotive Exhibition"),
    ("New York International Auto Show", "Motor show", "Greater New York Automobile Dealers Association", "United States", "Javits Center, New York", 4, "April", "https://www.autoshowny.com/", "New York International Auto Show"),
    ("Chicago Auto Show", "Motor show", "Chicago Automobile Trade Association", "United States", "McCormick Place, Chicago", 2, "February, the largest auto show in North America", "https://www.chicagoautoshow.com/", "Chicago Auto Show"),
    ("Detroit Auto Show", "Motor show", "Detroit Auto Dealers Association", "United States", "Huntington Place, Detroit", 1, "January", "https://detroitautoshow.com/", "Detroit Auto Show"),
    ("SEMA Show", "Motor show", "Specialty Equipment Market Association", "United States", "Las Vegas Convention Center", 11, "early November, trade only", "https://www.semashow.com/", "SEMA"),
    ("Essen Motor Show", "Motor show", "Messe Essen", "Germany", "Messe Essen", 12, "late November into December", "https://www.essen-motorshow.de/", "Essen Motor Show"),
    ("Techno-Classica Essen", "Motor show", "Messe Essen", "Germany", "Messe Essen", 4, "April", "https://www.siha.de/", "Techno Classica"),
    ("Rétromobile", "Motor show", "Comexposium", "France", "Paris Expo Porte de Versailles", 2, "early February", "https://en.retromobile.com/", "Rétromobile"),
    ("Autosport International", "Motor show", "Autosport", "United Kingdom", "NEC Birmingham", 1, "January", "https://www.autosportinternational.com/", "Autosport International"),
    ("Brussels Motor Show", "Motor show", "Febiac", "Belgium", "Brussels Expo", 1, "January", "https://www.autosalon.be/", "Brussels Motor Show"),
    ("CES mobility", "Motor show", "Consumer Technology Association", "United States", "Las Vegas Convention Center", 1, "early January", "https://www.ces.tech/", "Consumer Electronics Show"),
    ("Goodwood Festival of Speed Future Lab", "Motor show", "Goodwood", "United Kingdom", "Goodwood House, West Sussex", 7, "mid-July, inside the Festival of Speed", "https://www.goodwood.com/motorsport/festival-of-speed/", "Goodwood Festival of Speed"),

    # ---------------------------------------------------------------- Gatherings and road events
    ("Woodward Dream Cruise", "Gathering", "Woodward Dream Cruise", "United States", "Woodward Avenue, Detroit, Michigan", 8, "the third Saturday in August", "https://woodwarddreamcruise.com/", "Woodward Dream Cruise"),
    ("Hot Rod Power Tour", "Gathering", "Hot Rod", "United States", "A different route across the United States each year", 6, "June", "https://www.hotrod.com/", "Hot Rod Power Tour"),
    ("Gumball 3000", "Gathering", "Gumball 3000", "International", "A different intercontinental route each year", 5, "May or June", "https://gumball3000.com/", "Gumball 3000"),
    ("Cannonball Run Europe", "Gathering", "Independent", "International", "A different European route each year", 6, "summer", "https://www.cannonballrun.eu/", "Cannonball Run"),
    ("Nürburgring Touristenfahrten", "Gathering", "Nürburgring", "Germany", "Nürburgring Nordschleife", 3, "public lapping days from March to November", "https://nuerburgring.de/", "Nürburgring"),
    ("Caffeine and Machine gatherings", "Gathering", "Caffeine and Machine", "United Kingdom", "Ettington, Warwickshire", 1, "year round", "https://caffeineandmachine.com/", "Car meet"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-")


def get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


# A confirmed edition reads like "15-18 July 2027" or "July 15-18, 2027" in the article intro.
DATE_A = re.compile(r"\b(\d{1,2})\s*(?:[-–—]\s*(\d{1,2})\s*)?(" + "|".join(MONTHS[1:]) + r")\s+(20\d\d)\b")
DATE_B = re.compile(r"\b(" + "|".join(MONTHS[1:]) + r")\s+(\d{1,2})\s*(?:[-–—]\s*(\d{1,2}))?,?\s+(20\d\d)\b")


def parse_date(text):
    """Return (iso_start, human) for the soonest future date stated in the text, else None."""
    best = None
    for m in DATE_A.finditer(text or ""):
        d1, d2, mon, yr = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
        best = pick(best, yr, MONTHS.index(mon), d1, d2)
    for m in DATE_B.finditer(text or ""):
        mon, d1, d2, yr = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        best = pick(best, yr, MONTHS.index(mon), d1, d2)
    return best


def pick(best, yr, mon, d1, d2):
    if not (1 <= d1 <= 31 and yr >= TODAY.year):
        return best
    try:
        start = date(yr, mon, d1)
    except ValueError:
        return best
    if start < TODAY:
        return best
    human = f"{d1}" + (f"–{int(d2)}" if d2 else "") + f" {MONTHS[mon]} {yr}"
    cand = (start.isoformat(), human)
    return cand if best is None or cand[0] < best[0] else best


def soonest(a, b):
    """Of two (iso, human) dates, the earlier one; either may be None."""
    if a is None:
        return b
    if b is None:
        return a
    return b if b[0] < a[0] else a


def extracts(titles):
    """title -> article intro, batched 20 per request. Missing articles are simply absent."""
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        q = ("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
             "&prop=extracts&exintro=1&explaintext=1&exlimit=20&titles="
             + urllib.parse.quote("|".join(batch)))
        j = get(q)
        if not j:
            continue
        for page in (j.get("query", {}).get("pages", {}) or {}).values():
            ex = (page.get("extract") or "").strip()
            if ex:
                out[page.get("title", "")] = ex
        # normalise redirects back onto the title we asked for
        for r in (j.get("query", {}).get("redirects") or []):
            if r.get("to") in out:
                out[r.get("from")] = out[r["to"]]
        time.sleep(0.2)
    return out


def harvest():
    """Wikipedia per event: a fresh description, and a confirmed date when one is stated.

    The description comes from the evergreen article ("Monaco Grand Prix"), which is
    written in the present tense about the event in general and therefore almost never
    carries a date. The date of the next running lives in the year-prefixed edition
    article ("2027 Monaco Grand Prix": "scheduled to take place on 12-13 June 2027"),
    which is what English Wikipedia consistently names them. Asking only the evergreen
    article is why this harvest reported zero confirmed dates: both this year's and next
    year's edition are now requested alongside it, and the soonest future date wins.
    Editions that do not exist yet come back missing and cost nothing.
    """
    titles = sorted({e[8] for e in E})
    years = (TODAY.year, TODAY.year + 1)
    editions = {t: [f"{y} {t}" for y in years] for t in titles}
    raw = extracts(titles + [e for t in titles for e in editions[t]])

    out = {}
    for t in titles:
        ex = raw.get(t, "")
        d = None
        for e in editions[t]:
            d = soonest(d, parse_date(raw.get(e, "")[:1500]))
        if d is None:                      # a few evergreen articles do state the next date
            d = parse_date(ex[:1500])
        if ex or d:
            out[t] = {"extract": ex[:900], "date": d}

    if out:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(out, ensure_ascii=False))
    elif CACHE.exists():
        out = json.loads(CACHE.read_text())
    return out


def build_rows(wiki):
    rows = []
    for name, cat, series, country, place, mon, window, site, wt in E:
        w = wiki.get(wt) or {}
        d = w.get("date")
        rows.append({
            "n": name, "c": cat, "s": series, "co": country, "p": place,
            "m": mon, "mo": MONTHS[mon], "w": window, "u": "/events/" + slug(name) + "/",
            "site": site, "wiki": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(wt.replace(" ", "_")),
            "ex": (w.get("extract") or "").strip(),
            "d": d[0] if d else "", "dh": d[1] if d else "",
        })
    rows.sort(key=lambda r: (r["m"], r["n"]))
    return rows


# ------------------------------------------------------------------ rendering
def shell(title, desc, canon, body, extra_head="", extra_js=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0B0D10"><title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"><link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/assets/site.css">{extra_head}</head><body>
<header class="hdr"><div class="wrap hdr-in">
<a class="logo" href="/">Car<em>Verdict</em></a>
<div class="searchbox"><input id="q" type="search" placeholder="Search 17,000+ cars" autocomplete="off" aria-label="search"><div id="q-out" hidden></div></div>
<nav class="nav"><a href="/cars/">Browse</a><a href="/library/">Library</a><a href="/events/" class="cur">Events</a><a href="/play/">Play</a><a href="/calculators/">Calculators</a></nav>
</div></header>
{body}
<footer><div class="wrap"><p>Event descriptions from Wikipedia (CC BY-SA). Dates and ticketing are
confirmed by the organiser — always check the official site before booking travel. ·
<a href="/methodology/">Methodology</a></p></div></footer>
<script src="/assets/site.js" defer></script>{extra_js}</body></html>"""


def index_page(rows):
    cats = sorted({r["c"] for r in rows})
    countries = sorted({r["co"] for r in rows})
    confirmed = sum(1 for r in rows if r["d"])
    opts = lambda vals: "".join(f'<option value="{esc(v)}">{esc(v)}</option>' for v in vals)
    body = f"""<div class="hero lib-hero"><div class="wrap hero-inner">
<h1>The motoring calendar</h1>
<p class="sub">{len(rows)} events across {len(countries)} countries — Grands Prix, 24-hour races,
rallies, concours, auctions and motor shows. Confirmed dates appear here automatically the
moment organisers publish them{f" - {confirmed} confirmed so far" if confirmed else ""}; until
then each event shows the window it always occupies.</p></div></div>
<div class="wrap">
<div class="ev-controls">
<input id="ev-q" type="search" placeholder="Search events, venues, series…" aria-label="Search events">
<select id="ev-cat" aria-label="Category"><option value="">All categories</option>{opts(cats)}</select>
<select id="ev-co" aria-label="Country"><option value="">All countries</option>{opts(countries)}</select>
<select id="ev-mo" aria-label="Month"><option value="">All months</option>{opts(MONTHS[1:])}</select>
<button id="ev-soon" type="button" class="btn ghost">Confirmed dates only</button>
</div>
<p class="muted" id="ev-count"></p>
<div class="ev-grid" id="ev-grid"></div>
<p class="lib-note">Descriptions from Wikipedia (CC BY-SA). Dates are taken from the organiser or the
event's Wikipedia article and re-checked on every deploy; motorsport calendars change, so the official
site is always the last word.</p></div>
<script id="ev-data" type="application/json">{json.dumps(rows, ensure_ascii=False)}</script>"""
    return shell("Motor Events Calendar — Races, Concours, Auctions & Motor Shows Worldwide | " + BRAND,
                 f"A searchable calendar of {len(rows)} motoring events worldwide: Formula 1, Le Mans, "
                 "MotoGP, rallies, concours d'elegance, collector car auctions and motor shows, with "
                 "dates, venues and official ticket links.",
                 f"{ORIGIN}/events/", body, extra_js='<script src="/assets/events.js" defer></script>')


def event_page(r, rows):
    when = (f'<b>{esc(r["dh"])}</b> <span class="ev-badge ok">confirmed</span>' if r["dh"]
            else f'Usually {esc(r["w"])} <span class="ev-badge">date not yet confirmed</span>')
    near = [x for x in rows if x is not r and (x["co"] == r["co"] or x["c"] == r["c"])][:9]
    rel = "".join(f'<a href="{x["u"]}">{esc(x["n"])}<small>{esc(x["mo"])} · {esc(x["co"])}</small></a>'
                  for x in near)
    ex = f'<p>{esc(r["ex"])}</p>' if r["ex"] else ""
    # Breadcrumbs are emitted for every event, dated or not - the trail is a property of the
    # page, not of whether organisers have published next year's date yet.
    ld = ('<script type="application/ld+json">' + json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"},
            {"@type": "ListItem", "position": 2, "name": "Events", "item": ORIGIN + "/events/"},
            {"@type": "ListItem", "position": 3, "name": r["n"], "item": ORIGIN + r["u"]}],
    }, ensure_ascii=False) + "</script>")
    if r["d"]:
        ld += ('<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "Event", "name": r["n"],
            "startDate": r["d"], "eventStatus": "https://schema.org/EventScheduled",
            "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
            "location": {"@type": "Place", "name": r["p"],
                         "address": {"@type": "PostalAddress", "addressCountry": r["co"]}},
            "description": (r["ex"] or r["n"])[:300], "url": ORIGIN + r["u"],
        }, ensure_ascii=False) + "</script>")
    body = f"""<div class="wrap ev-page">
<nav class="crumbs"><a href="/">Home</a> › <a href="/events/">Events</a> › <span>{esc(r["n"])}</span></nav>
<h1>{esc(r["n"])}</h1>
<p class="sub">{esc(r["s"])} · {esc(r["p"])}, {esc(r["co"])}</p>
<div class="ev-facts">
<div><span>When</span>{when}</div>
<div><span>Where</span>{esc(r["p"])}, {esc(r["co"])}</div>
<div><span>Category</span><a href="/events/?cat={urllib.parse.quote(r["c"])}">{esc(r["c"])}</a></div>
<div><span>Series</span>{esc(r["s"])}</div>
</div>
<div class="ev-cta">
<a class="btn" href="{esc(r["site"])}" rel="nofollow noopener" target="_blank">Official site and tickets</a>
<a class="btn ghost" href="{esc(r["wiki"])}" rel="noopener" target="_blank">Read the full history</a>
<a class="btn ghost" href="https://www.google.com/maps/search/{urllib.parse.quote(r["p"] + ", " + r["co"])}" rel="nofollow noopener" target="_blank">Find the venue</a>
</div>
<h2>About the event</h2>{ex}
<p class="muted">Typical window: {esc(r["w"])}. Organisers publish the following year's date at different
points in the season — the official site above is the authority. This page is rebuilt on every deploy,
so a confirmed date appears here as soon as it is public.</p>
<h2>Also worth the trip</h2><div class="rel-grid">{rel}</div>
</div>{ld}"""
    desc = (f'{r["n"]}: {r["s"]} at {r["p"]}, {r["co"]}. '
            + (f'Next edition {r["dh"]}. ' if r["dh"] else f'Usually held {r["w"]}. ')
            + "Dates, venue and official ticket links.")
    return shell(f'{r["n"]} — Dates, Venue & Tickets | {BRAND}', desc, ORIGIN + r["u"], body)


def main():
    wiki = harvest()
    rows = build_rows(wiki)
    (SITE / "events").mkdir(parents=True, exist_ok=True)
    (SITE / "events" / "index.html").write_text(index_page(rows))
    for r in rows:
        p = SITE / r["u"].strip("/") / "index.html"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(event_page(r, rows))
    (SITE / "assets").mkdir(parents=True, exist_ok=True)
    (SITE / "assets" / "events.json").write_text(json.dumps(rows, ensure_ascii=False,
                                                           separators=(",", ":")))
    dated = sum(1 for r in rows if r["d"])
    print(f"EVENTS OK: {len(rows)} events, {dated} with a confirmed date, "
          f"{len({r['co'] for r in rows})} countries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
