@echo off
echo ====================================
echo Shodo Ecosystem Logs
echo ====================================
echo.
echo Press Ctrl+C to stop viewing logs
echo.

docker-compose -f docker-compose.windows.yml logs -f