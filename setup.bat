@echo off
title Chatbot Kurulumu

echo Chatbot Kurulum Script'i Baslatiliyor...
echo -----------------------------------------

REM Python komutunun varligini kontrol et
python --version >nul 2>nul
if %errorlevel% neq 0 (
    echo HATA: Python bulunamadi.
    echo Lutfen Python'u yukleyin ve PATH'e eklediginizden emin olun.
    echo.
    pause
    exit /b
)

REM Sanal ortam klasorunun olup olmadigini kontrol et
if not exist venv (
    echo Sanal ortam olusturuluyor...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo HATA: Sanal ortam olusturulamadi. Komut istemini yonetici olarak calistirmayi deneyin.
        echo.
        pause
        exit /b
    )
    echo Sanal ortam basariyla olusturuldu.
) else (
    echo Mevcut sanal ortam bulundu.
)

REM Kutuphaneleri yukle
echo.
echo Kutuphaneler requirements.txt dosyasindan yukleniyor...
echo Bu islem internet hiziniza ve bilgisayariniza bagli olarak uzun surebilir.
call venv\Scripts\activate.bat
python -m pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo HATA: Kutuphaneler yuklenirken bir sorun olustu.
    echo Lutfen yukaridaki hata mesajlarini kontrol edin.
    echo.
    pause
    exit /b
)

echo.
echo -----------------------------------------
echo Kurulum basariyla tamamlandi!
echo -----------------------------------------
echo.
echo Uygulamayi baslatmak icin 'start.bat' dosyasina cift tiklayabilirsiniz.
echo.
pause
