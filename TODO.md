# Projekt TODO (MVP -> V1)

## 1. Osnovna arhitektura (MVP)
- [ ] Izbrana tehnologija: Python + FastAPI + preprost HTML/CSS/JS frontend.
- [ ] Definirati modele: predmet/tema/poglavje/nivo, test, vprašanje, odgovor, ocena, vrzeli.
- [ ] Dodati API endpoint za generiranje testa prek ChatGPT.
- [ ] Dodati API endpoint za ocenjevanje odgovorov in analizo vrzeli.
- [ ] Vmesno hranjenje testov (in-memory), kasneje prehod na bazo.

## 2. Prompting in kvaliteta vsebine
- [ ] Pripraviti sistemske promte v slovenščini za:
- [ ] generiranje vprašanj po nivojih gimnazije,
- [ ] ocenjevanje kratkih in daljših odgovorov,
- [ ] odkrivanje vrzeli in predlogov za učenje.
- [ ] Uvesti strukturiran JSON izhod in validacijo.
- [ ] Dodati zaščite pred neveljavnimi/nepopolnimi odgovori modela.

## 3. Uporabniški tok (web)
- [ ] Stran 1: vnos tema/poglavje/nivo.
- [ ] Stran 2: reševanje testa.
- [ ] Stran 3: rezultat, točke, razlaga napak, vrzeli znanja.
- [ ] Dodati prikaz priporočil za nadaljnje učenje (v slovenščini).

## 4. Učni materiali
- [ ] Endpoint za pripravo kratkega učnega načrta glede na vrzeli.
- [ ] Generiranje povzetka snovi, mini razlage, in dodatnih vaj.
- [ ] Možnost izvoza učnega lista (PDF ali Markdown).

## 5. Varnost in stroški
- [ ] API ključ izključno preko okoljske spremenljivke.
- [ ] Omejitev dolžine vhodov (tema/poglavje) in osnovni rate limiting.
- [ ] Logiranje brez osebnih podatkov.
- [ ] Dodati budget guardrails (npr. max število vprašanj / max tokeni).

## 6. Testiranje in kvaliteta
- [ ] Unit testi za validacijo modelov in parsing AI izhoda.
- [ ] Integracijski testi za API tok (generate -> answer -> grade).
- [ ] Testi za robne primere (prazni odgovori, zelo kratki odgovori, neveljaven JSON).

## 7. Priprava na produkcijo
- [ ] Persistenca (PostgreSQL) za zgodovino testov.
- [ ] Avtentikacija (učenci/učitelji) in osnovna administracija.
- [ ] Docker + CI pipeline.
- [ ] Monitoring (napake, latenca, poraba API klicev).
