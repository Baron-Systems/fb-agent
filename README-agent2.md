# Frappe Manager Backup Agent (fb-agent)

**وكيل نسخ احتياطي بدون إعداد لسيرفرات Frappe Manager.**

Zero-config backup agent for Frappe Manager production servers.

---

## المميزات / Features

- 🎯 **بدون إعداد:** يكتشف تلقائياً `fm` والمواقع واللوحة
- 🔐 **آمن:** توقيع HMAC، إجراءات مسموحة فقط
- 🔄 **تسجيل تلقائي:** يعلن عن نفسه للوحة كل 5 دقائق
- 🛡️ **آمن:** كل العمليات عبر `fm shell` — لا وصول مباشر لـ docker/bench
- 📡 **خفيف:** استهلاك موارد قليل
- 🔍 **اكتشاف:** ي parse مخرجات `fm list` لاكتشاف المواقع تلقائياً

---

## البدء السريع / Quick Start

```bash
# تثبيت
pipx install git+https://github.com/Baron-Systems/fb-agent.git

# تشغيل (يبدأ على المنفذ 8888)
fb-agent run
```

الوكيل يقوم تلقائياً بـ:

1. إيجاد `fm` في PATH
2. إنشاء معرف وكيل ثابت
3. اكتشاف اللوحة عبر UDP broadcast
4. التسجيل في اللوحة
5. تشغيل خادم API
6. إعادة الإعلان كل 5 دقائق

---

## المتطلبات / Requirements

- Python 3.11+
- `fm` (Frappe Manager) في PATH
- لوحة التحكم (`fb`) تعمل على نفس الشبكة

---

## الإجراءات المدعومة / Supported Actions

الوكيل يقبل فقط هذه الإجراءات المسموحة:

| الإجراء | الوصف |
|---------|--------|
| `list_sites` | اكتشاف المواقع عبر `fm list` |
| `backup_site` | تنفيذ النسخ الاحتياطي عبر `fm shell` + `bench backup` |
| `download_artifact` | تحميل ملفات النسخ الاحتياطي |
| `health` | فحص الصحة |

---

## تنفيذ النسخ الاحتياطي / Backup Execution

```
المستخدم يضغط "Backup" في لوحة التحكم
         ↓
اللوحة → الوكيل (POST /api/backup_site)
         ↓
الوكيل يتحقق من اسم الموقع
         ↓
تنفيذ عبر PTY:
  fm shell <site>
  bench --site <site> backup
  exit
         ↓
الوكيل يعيد artifacts النسخ الاحتياطي
         ↓
اللوحة تسحب الملفات إلى التخزين
```

---

## خدمة systemd / systemd Service

```bash
# تثبيت كخدمة
sudo curl -o /etc/systemd/system/fb-agent.service \
  https://raw.githubusercontent.com/Baron-Systems/fb-agent/main/fb-agent.service

sudo systemctl daemon-reload
sudo systemctl enable --now fb-agent
```

---

## مواقع البيانات / Data Locations

| الغرض | المسار |
|-------|--------|
| الحالة | `~/.local/share/fb-agent/` |
| المفتاح المشترك | `~/.local/share/fb-agent/shared_secret.txt` |

---

## الأمان / Security

- ✅ توقيع الطلبات بـ HMAC مع timestamp
- ✅ إجراءات مسموحة فقط (allowlist)
- ✅ التحقق من المدخلات (أسماء المواقع، المسارات)
- ✅ لا تنفيذ أوامر عشوائية
- ✅ العمليات فقط عبر `fm shell`
- ✅ ملفات النسخ الاحتياطي مقيدة بمسارات `private/backups`

---

## استكشاف الأخطاء / Troubleshooting

### الوكيل لا يجد fm

```bash
# التحقق من وجود fm في PATH
which fm

# أو إنشاء symlink
sudo ln -s /path/to/fm /usr/local/bin/fm
```

### الوكيل لا يتصل باللوحة

1. تأكد أن اللوحة تعمل: `curl http://dashboard_ip:7311/`
2. تأكد أن الجدار الناري يسمح بالمنفذ 8888
3. راجع السجلات: `journalctl -u fb-agent -n 50`

---

## التطوير / Development

```bash
git clone https://github.com/Baron-Systems/fb-agent.git
cd fb-agent

pip install -e .
python -m fb_agent.cli
```

---

## التوثيق / Documentation

- [دليل التثبيت (fb)](../fb/INSTALL.md)

---

## الترخيص / License

Proprietary

## الدعم / Support

Issues: https://github.com/Baron-Systems/fb-agent/issues
