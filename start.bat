@echo off
REM Bu satir, komutlarin ekranda gorunmesini engeller.

TITLE Flask Uygulama Baslatici

ECHO Sanal ortam aktive ediliyor...
ECHO.

REM --- Sanal Ortam Aktivasyonu ---
REM Asagidaki satir, 'venv' adli klasordeki sanal ortami aktive eder.
REM Eger sanal ortam klasorunuzun adi farkliysa ('env' gibi),
REM asagidaki 'venv' kismini kendi klasor adinizla degistirin.
CALL venv\Scripts\activate.bat

ECHO.
ECHO Flask uygulamasi ve e-posta servisi baslatiliyor...
ECHO.

REM Python betigini calistirir.
REM Sanal ortam aktive edildigi icin, bu komut sanal ortamdaki Python'u kullanacaktir.
python start_all.py

ECHO.
ECHO Betik calismasi durdu veya bir hata olustu.
REM Pencerenin hemen kapanmamasi icin kullanici girisi bekler.
pause
