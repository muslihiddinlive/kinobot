#!/bin/bash
# YoqolganRobot — avtomatik o'rnatish skripti

echo "🚀 YoqolganRobot o'rnatilmoqda..."

# Python tekshirish
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 topilmadi. O'rnating: sudo apt install python3"
    exit 1
fi

# pip o'rnatish
pip3 install -r requirements.txt

# .env fayl
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚙️  .env fayl yaratildi. Quyidagilarni to'ldiring:"
    echo "   BOT_TOKEN=your_token"
    echo "   ADMIN_IDS=your_id"
    echo "   WEBHOOK_DOMAIN=https://yourdomain.com"
    echo ""
    echo "Tahrirlash: nano .env"
else
    echo "✅ .env fayl mavjud"
fi

echo ""
echo "✅ O'rnatish tugadi!"
echo "▶️  Ishga tushirish: python3 bot.py"
