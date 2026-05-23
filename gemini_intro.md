Jeśli budujemy kokpit makro dla kogoś, kto zarządza globalnym portfelem zdywersyfikowanym, interesują Cię nie tyle same nominalne ceny, ile **relatywna siła, spready, rotacja kapitału i sygnały płynnościowe**.

Skoro silnikiem pod spodem jest Python zbierający dane z yfinance bez wsparcia LLM, musimy wycisnąć maksimum z czystej matematyki (proste operacje na tickerach, wyliczanie wskaźników i spreadów w locie).

Oto profesjonalna mapa surowców informacyjnych, które powinny znaleźć się na tym ekranie o 7:00 rano.

---

## 1. Sovereign Fixed Income (Krzywa i Spready Bazowe)

Ponieważ Yahoo Finance ma ograniczenia w dostępie do ciągłych rentowności spot dla Europy, najlepszym instytucjonalnym podejściem porannym jest obserwacja **krzywej USA (w rentownościach)** oraz **płynnościowych kontraktów futures (cenowych) na Europę**, z których matematycznie wyciągamy spready.

### Rentowności USA (Term Structure)

Zamiast pojedynczych punktów, dashboard powinien pokazywać nachylenie krzywej (Yield Curve Slope), czyli matematyczne spready wyliczane w locie:

* `^IRX` (US 3-Month Bill) – stopa wolna od ryzyka / front-end / oczekiwania wobec Fed.
* `^FVX` (US 5-Year Note) – brzuch krzywej.
* `^TNX` (US 10-Year Note) – globalny benchmark.
* `^TYX` (US 30-Year Bond) – długi koniec / term premium i oczekiwania inflacyjne.

> **Wskaźnik Makro (Wyliczany w kodzie):**
> * **Krzywa 5s30s:** `^TYX` minus `^FVX` (wskaźnik flattener/steepener).
> * **Krzywa 3M10Y:** `^TNX` minus `^IRX` (klasyczny wskaźnik recesyjny).
> 
> 

### Europa (Sovereign Risk Premiums)

Tu operujemy na czołowych kontraktach terminowych. Ponieważ cena obligacji porusza się odwrotnie do rentowności, spadek ceny kontraktu oznacza wzrost rentowności.

* `FGBL.F` (Euro-Bund Futures, 10Y) – niemiecki core rynek.
* `FOAT.F` (Euro-OAT Futures, 10Y) – Francja (ryzyko fiskalne/polityczne strefy euro).
* `FBTP.F` (Euro-BTP Futures, 10Y) – Włochy (peryferia / barometr apetytu na ryzyko kredytowe w Europie).

> **Wskaźnik Makro (Wyliczany w kodzie):**
> * **BTP-Bund Spread Proxy:** Procentowa zmiana `FBTP.F` podzielona przez procentową zmianę `FGBL.F` (lub bezpośrednia różnica w dziennej stopie zwrotu). Jeśli BTP spada silniej niż Bund, rano wiesz, że spready w Europie się rozszerzają (Risk-Off).
> * **OAT-Bund Spread Proxy:** Analogicznie relacja `FOAT.F` do `FGBL.F` – kluczowa do monitorowania systemowego stresu we Francji.
> 
> 

---

## 2. Credit Markets & Risk Premiums (Korporacje i EM)

Skoro nie mamy bezpośrednich tickerów na spready kredytowe (jak ICE BofA Spreads z FREDa), izolujemy ryzyko kredytowe poprzez **relatywną siłę (Ratios)** najbardziej płynnych ETF-ów dłużnych w zestawieniu z obligacjami rządowymi (safe havens).

| Ticker | Klasa Aktywów | Rola na dashboardzie |
| --- | --- | --- |
| `LQD` | US Investment Grade | Czyste ryzyko korporacyjne o wysokim ratingu (wrażliwe na duration). |
| `HYG` | US High Yield | Czyste ryzyko kredytowe / barometr default premium (niska wrażliwość na duration). |
| `EMB` | JPM EMBI (Hard Currency) | Dług Emerging Markets w USD (ryzyko suwerenne EM bez ryzyka walutowego). |
| `IETF.L` / `IEAC.L` | Euro Corporate / HY | Odpowiedniki europejskie (UCITS), jeśli chcesz widzieć poranny sentyment na kredycie w EUR. |

> **Wskaźnik Makro (Wyliczany w kodzie):**
> * **Pure Credit Appetite:** Stosunek `HYG / IEI` (gdzie `IEI` to US Treasury 3-7 Year). Jeśli ten współczynnik rośnie, spready kredytowe się zwężają, kapitał wchodzi w ryzyko.
> * **EM Distress Engine:** Relacja `EMB / TLT` – pokazuje, czy rynki wschodzące dostają mocniej niż bezpieczne długie obligacje USA.
> 
> 

---

## 3. US Equity Sector & Factor Rotation (Cykl Koniunkturalny)

Dla funduszu long-only rotacja sektorowa w USA to wiodący indykator tego, w jakiej fazie cyklu jesteśmy. Zamiast patrzeć na S&P 500, rozbijamy rynek na 11 sektorów SPDR i wyliczamy relacje między nimi.

### Sektory Cykliczne / Reflacyjne (Beta & Growth):

* `XLK` (Technology) – wyceny oparte na długim duration, wrażliwe na stopy.
* `XLF` (Financials) – beneficjent stromego kształtu krzywej dochodowości.
* `XLI` (Industrials) & `XLB` (Materials) – czysty globalny wzrost gospodarczy / CAPEX.
* `XLY` (Consumer Discretionary) – kondycja amerykańskiego konsumenta.
* `XLE` (Energy) & `XLC` (Communication Services).

### Sektory Defensywne (Value & Value-Proxy):

* `XLP` (Consumer Staples) & `XLV` (Healthcare) – bezpieczne przystanie.
* `XLU` (Utilities) & `XLRE` (Real Estate) – sektory traktowane jak "bond proxies" (rentowne, gdy stopy spadają).

> **Wskaźnik Makro (Wyliczany w kodzie):**
> * **Cyclicals vs Defensives:** `XLY / XLP` (Konsumpcja dyskrecjonalna vs podstawowa). Najlepszy rynkowy wskaźnik "Risk-On / Risk-Off" w akcjach.
> * **Duration Play:** `XLK / XLY` lub `XLK / XLI`.
> * **Value vs Growth:** Stosunek `IWD` (iShares Russell 1000 Value) do `IWF` (Growth).
> 
> 

---

## 4. FX & Global Liquidity (Przekaźniki Makro)

Dla globalnego portfela ruchy na walutach to nie tylko kwestia FX hedgingu, ale przede wszystkim sygnał o globalnej płynności i kierunku przepływu kapitału.

* `DX-Y.NYB` (DXY) – Indeks Dolara. Absolutna baza. Gdy DXY rośnie, globalna płynność się kurczy.
* `USDJPY=X` – **Kotwica Globalnego Carry Trade**. Kluczowa waluta finansująca. Jeśli JPY gwałtownie się umacnia (para spada), oznacza to ucieczkę z carry trade i przymusową likwidację pozycji na ryzykownych aktywach.
* `USDCNH=X` – Offshore Yuan. Najważniejszy indykator dla Azji i Emerging Markets. Osłabienie Juana (wzrost pary) automatycznie wywiera presję na surowce i waluty EM.
* `AUDJPY=X` – Cross walutowy będący czystym barometrem sentymentu (Pro-growth AUD vs Safe-haven JPY).
* **High-Yielding EM FX Proxies:** `USDMXN=X` (Meksyk) lub `USDBRL=X` (Brazylia) – rano pokazują, czy kapitał ucieka z rynków o wysokiej stopie procentowej.

---

## 5. Commodities (Wzrost vs Inflacja)

Surowce traktujemy jako indykatory wyprzedzające dla inflacji oraz realnego popytu w przemyśle.

* `HG=F` (Miedź / "Dr. Copper") – najważniejszy surowiec przemysłowy, barometr globalnego przetwórstwa (szczególnie Chin).
* `GC=F` (Złoto) – realne stopy procentowe (odwrócona korelacja) i ryzyko geopolityczne.
* `CL=F` (WTI) / `BZ=F` (Brent) – komponent kosztowy i presja inflacyjna.

> **Wskaźnik Makro (Wyliczany w kodzie):**
> * **Copper/Gold Ratio:** `HG=F / GC=F`. Klasyczny wskaźnik Gundlacha. Kiedy rośnie, oznacza to jednoczesny wzrost wzrostu gospodarczego i rentowności obligacji. Kiedy spada – gospodarka hamuje, a kapitał ucieka w fixed income.
> 
> 

---

### Podsumowanie: Co skrypt powinien zrobić z tym rano?

Zamiast tabeli z cenami z yfinance, Twój skrypt w Pythonie powinien agregować te dane w **"Macro Regimes Matrix"**.

Przykładowo, sekcja Fixed Income na dashboardzie powinna od razu wyświetlać wyliczone delty spreadów (np. *US 2s10s: -12bps [Flattening 1D]*), a sekcja akcyjna zamiast suchych wyników sektorów powinna pokazywać zachowanie wskaźników relatywnych (np. *Cyclicals/Defensives: +0.45% [Risk-On Expansion]*).