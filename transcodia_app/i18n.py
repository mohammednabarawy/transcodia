"""Arabic interface translations with retained media-format identifiers."""
from PySide6 import QtCore, QtGui, QtWidgets

AR = {
    "Cancelled": "تم الإلغاء",
    "Appearance": "المظهر",
    "Task": "المهمة", "Skin": "المظهر", "Language": "اللغة", "Settings": "الخيارات", "Help": "مساعدة",
    "Output Folder": "مجلد الإخراج", "Option": "الخيارات", "Remove": "إزالة", "Clear List": "حذف القائمة",
    "Stop": "إيقاف", "Start": "بدء", "Pause": "إيقاف مؤقت", "Resume": "استئناف", "Home Page": "الصفحة الرئيسية",
    "Video": "الفيديو", "Audio": "الصوت", "Picture": "الصورة", "Document": "وثيقة",
    "ROM Device / DVD / CD / ISO": "أجهزة القراءة \\ دي في دي \\ سي دي \\ آيسو", "Utilities": "الأدوات المساعدة",
    "Video Joiner & Mux": "دامج الفيديو & Mux", "Splitter": "الفاصل", "Clip": "قص", "Fast Clip": "مقطع سريع",
    "Delogo": "إزالة العلامة\nالمائية", "Export Frames": "إطارات\nالتصدير", "Screen Recorder": "مسجل\nالشاشة",
    "Video Downloader": "تنزيل الفيديو", "Audio Joiner & Mix": "دمج الصوت", "Batch Resize & Transform": "تغيير حجم الصور",
    "Media\nPlayer": "مشغل\nالوسائط",
    "Your media. Your next format.": "وسائطك، بصيغتك التالية.",
    "Conversion queue": "قائمة التحويل",
    "Ready for your next conversion": "جاهز لعملية التحويل التالية",
    "Drop files here or choose a tool to begin.": "أفلت الملفات هنا أو اختر أداة للبدء.",
    "Build a single PDF": "اجمع مستنداتك في ملف PDF واحد",
    "Add documents, arrange their order, and choose an output folder.": "أضف المستندات ورتّبها ثم اختر مجلد الإخراج.",
    "Preview": "عرض", "Source": "المصدر", "Output / Convert State": "الإخراج / حالة التحويل",
    "Pending": "انتظار", "Completed": "اكتمل", "Failed": "فشل", "Converting...": "جارٍ التحويل...",
    "Add Files": "إضافة ملفات", "Add Folder": "إضافة مجلد", "OK": "موافق", "Cancel": "إلغاء",
    "Media information": "Media information", "Append setting name": "اسم الإعدادات المرفقة",
    "Completion notification": "إشعار بالاكتمال", "Elapsed Time": "الوقت المنقضي",
    "After Converting: Shut down computer": "بعدالتحويل : إيقاف تشغيل الكمبيوتر",
    "Move Up": "تحريك لأعلى", "Move Down": "تحريك لأسفل", "Remove Selected": "إزالة المحدد",
}

def tr(text: str, language: str = "ar") -> str:
    return AR.get(text, text) if language == "ar" else text

def apply_language(root: QtWidgets.QWidget, language: str):
    for obj in [root, *root.findChildren(QtCore.QObject)]:
        if isinstance(obj, (QtWidgets.QAbstractButton, QtWidgets.QLabel, QtGui.QAction)):
            source = obj.property("sourceText")
            if source is None:
                source = obj.text()
                obj.setProperty("sourceText", source)
            obj.setText(tr(source, language))
