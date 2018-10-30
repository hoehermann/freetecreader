# freetecreader
Dies ist eine Quelloffene Lesesoftware für den [FreeTec NC7004 "USB-Temperatur- &amp; Luftfeuchtigkeits-Datenlogger V2"](http://www.free-tec.de/USB-Temperatur-NC-7004-919.shtml) von [Pearl](https://www.pearl.de/a-NC7004-3044.shtml).

Die offizielle Software für den NC7004 heißt "DataLogger3.3". Die Software verwendet eine Variante der "EasyWeather" Bibliothek.
Der NC7004 ist allerdings nicht protokollkompatibel mit den [populären WH1080 Wetterstationen](http://www.weewx.com/hwcmp.html).
Hilfreich war [dieses Blog](https://baublog.ozerov.de/2011/12/software-fuer-meine-wetterstation-wh1080) mit Hinweis auf das Projekt [weatherpoller](https://code.google.com/archive/p/weatherpoller) mit dem Verweis auf [Jim Easterbrook's Weather station memory map](http://www.jim-easterbrook.me.uk/weather/mm).

Getestet unter Linux mit Python 3.6.6 und hidapi 0.2.1.  
Bitte beachten: Diese Software funktioniert zwar für das mir vorliegende Gerät, ich garantiere aber in keiner Weise für Zuverlässigkeit oder Korrektheit der Daten.
