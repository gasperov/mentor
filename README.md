# LearnMe (MVP Scaffold)

Spletna aplikacija za:
- generiranje testa po temi/poglavju/nivoju,
- resevanje testa v brskalniku,
- ocenjevanje odgovorov in odkrivanje vrzeli znanja,
- vse v slovenscini.

## Zakaj Python (in ne Go)?
- hitrejsi MVP za AI tokove (prompting + JSON validacija),
- bolj zrel ekosistem za LLM integracije,
- FastAPI omogoca hiter prehod od prototipa do produkcije.

## Zagon
1. Ustvari virtualno okolje in namesti pakete:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Nastavi okolje:
```bash
copy .env.example .env
```
V `.env` nastavi `OPENAI_API_KEY`.
Privzet model je `gpt-5` (visja kakovost). Ce model ni na voljo za tvoj racun, sistem samodejno preklopi na `gpt-4.1`.

3. Zazeni streznik:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

4. Odpri:
- `http://127.0.0.1:8001`
- API docs: `http://127.0.0.1:8001/docs`

## Trenutni API
- `POST /api/tests/generate`
- `POST /api/tests/grade`
- `GET /api/progress`

`POST /api/tests/grade` podpira:
- JSON (`test_id`, `answers`) ali
- `multipart/form-data` (`test_id`, `answers_json`, `image_<question_id>` datoteke).

Ce `OPENAI_API_KEY` ni nastavljen, aplikacija uporablja mock nacin (da lahko frontend tok deluje takoj).

## Adaptivno ponavljanje
- Frontend uporablja runtime `X-Session-Id` (samo med odprto stranjo).
- Znotraj seje sistem:
- ne ponavlja prejsnjih vprasanj,
- po ocenjevanju shrani vrzeli in jih poudari v naslednjem testu.
- Ob reloadu ali zaprtju browserja/taba je seja pozabljena (nov zacetek).
- Menjava tema/poglavje/nivo samodejno resetira sejo, da se stanja ne mesajo med temami.

## Shranjevanje napredka
- Napredek (rezultati poskusov) se shranjuje v `data/progress.json`.
- Dodatni tabelarni log ocen se shranjuje v `data/progress.txt`.
- Identiteta ucenca je anonimni `X-Student-Id` iz `localStorage`.
- Tako se ob ponovnem odprtju brskalnika vidi zgodovina napredka.

## Nakljucnost testov
- Generiranje uporablja variacijski marker in nakljucni pristop, zato novi testi niso vedno enaki.
- Podobna vprasanja so dovoljena, natancne ponovitve znotraj seje so blokirane.

## Odgovori s sliko (telefon)
- Pri vsakem vprasanju lahko dodas sliko odgovora.
- Na mobilnem telefonu input odpre kamero (`capture=environment`), da lahko takoj poslikas nalogo.
- Ob oddaji se slika poslje skupaj z odgovori in se doda kot oznacen slikovni odgovor za to vprasanje.

## Ocenjevanje
- Pri vsakem vprasanju rezultat zdaj vsebuje tudi `Popoln odgovor (100%)`, ki prikaze primer idealnega odgovora.

## Preprecevanje spanja racunalnika
- Na Windows sistemu aplikacija med delovanjem backend procesa zahteva, da sistem ne zaspi.
- Ko backend ustavis, se nastavitev samodejno sprosti.

## Predlagana naslednja iteracija
- persistenca (PostgreSQL),
- boljsi prompti + strozja JSON shema,
- locen endpoint za pripravo ucnega materiala po vrzelih,
- avtorizacija uporabnikov (ucenec/ucitelj).

## Licenca
Projekt je licenciran pod MIT licenco. Glej datoteko `LICENSE`.
