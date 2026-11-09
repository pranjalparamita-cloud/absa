"""
product_visuals.py — Product-type-specific generated studio visuals.
-------------------------------------------------------------------
Every listing has a visual that is selected from its actual product_type, not
only its broad category. For example: brake pads render as brake pads, air
fryers as air fryers, headphones as headphones, and running shoes as shoes.

These are generated visual previews for the demo catalog. They are deliberately
not copied retailer photos or claimed to depict an exact branded SKU.
"""
import base64
import hashlib
import html

PALETTES = [
    ("#6657d9", "#a78bfa", "#f3e8ff"), ("#0f766e", "#5eead4", "#e6fffb"),
    ("#1d4ed8", "#93c5fd", "#eaf2ff"), ("#be185d", "#f9a8d4", "#fff0f6"),
    ("#b45309", "#fcd34d", "#fff8e7"), ("#475569", "#cbd5e1", "#f8fafc"),
]


def _palette(product):
    key = str(product.get("sku", product.get("id", "catalog"))).encode()
    return PALETTES[int(hashlib.sha256(key).hexdigest()[:8], 16) % len(PALETTES)]


def _transform(view):
    if view == "angle":
        return "translate(20,-5) skewX(-8)"
    if view == "detail":
        return "translate(0,-8) scale(1.08)"
    return ""


def _screen(primary, secondary, stand=True):
    stand_svg = ("<path d='M236 276h48l18 32H218z' fill='{0}'/><rect x='174' y='307' width='172' height='13' rx='6' fill='#334155'/>".format(primary)
                 if stand else "")
    return f"""<rect x='125' y='72' width='270' height='188' rx='15' fill='{primary}'/>
      <rect x='142' y='89' width='236' height='152' rx='8' fill='#19233f'/>
      <rect x='153' y='101' width='214' height='128' rx='5' fill='{secondary}' opacity='.82'/>{stand_svg}"""


def _camera(primary, secondary):
    return f"""<rect x='126' y='132' width='268' height='156' rx='25' fill='{primary}'/>
      <path d='M182 132l22-38h110l22 38' fill='{primary}'/><circle cx='260' cy='210' r='65' fill='#17213c'/>
      <circle cx='260' cy='210' r='48' fill='{secondary}'/><circle cx='260' cy='210' r='29' fill='#eaf2ff'/>
      <rect x='326' y='151' width='35' height='20' rx='5' fill='#fff' opacity='.82'/>"""


def _headphones(primary, secondary):
    return f"""<path d='M151 219v-31c0-77 48-123 109-123s109 46 109 123v31' fill='none' stroke='{primary}' stroke-width='31' stroke-linecap='round'/>
      <rect x='125' y='205' width='67' height='104' rx='28' fill='{primary}'/><rect x='328' y='205' width='67' height='104' rx='28' fill='{primary}'/>
      <rect x='142' y='221' width='33' height='71' rx='16' fill='{secondary}'/><rect x='345' y='221' width='33' height='71' rx='16' fill='{secondary}'/>"""


def _speaker(primary, secondary, soundbar=False):
    if soundbar:
        return f"""<rect x='92' y='169' width='336' height='76' rx='26' fill='{primary}'/>
          <circle cx='142' cy='207' r='23' fill='{secondary}'/><circle cx='378' cy='207' r='23' fill='{secondary}'/>
          <circle cx='206' cy='207' r='12' fill='#fff' opacity='.7'/><circle cx='314' cy='207' r='12' fill='#fff' opacity='.7'/>"""
    return f"""<rect x='171' y='53' width='178' height='271' rx='33' fill='{primary}'/>
      <circle cx='260' cy='151' r='53' fill='#1e293b'/><circle cx='260' cy='151' r='33' fill='{secondary}'/>
      <circle cx='260' cy='258' r='35' fill='#1e293b'/><circle cx='260' cy='258' r='18' fill='{secondary}'/>"""


def _phone(primary, secondary, accessory="phone"):
    phone = f"""<rect x='195' y='42' width='130' height='276' rx='24' fill='{primary}'/>
      <rect x='207' y='59' width='106' height='240' rx='16' fill='#15213d'/><rect x='216' y='78' width='88' height='180' rx='10' fill='{secondary}' opacity='.75'/>
      <circle cx='260' cy='278' r='8' fill='#fff' opacity='.85'/>"""
    if accessory == "case":
        return phone + f"<path d='M187 62h13v239h-13c-15 0-27-12-27-27V89c0-15 12-27 27-27z' fill='{secondary}' opacity='.95'/>"
    if accessory == "stand":
        return phone + f"<path d='M219 318l-35 34h152l-35-34z' fill='{primary}'/><rect x='244' y='317' width='32' height='35' fill='{secondary}'/>"
    if accessory == "mount":
        return phone + f"<circle cx='260' cy='352' r='42' fill='{primary}'/><path d='M260 317v35m-26 0h52' stroke='{secondary}' stroke-width='10' stroke-linecap='round'/>"
    return phone


def _charger(primary, secondary, cable=False):
    cable_path = "<path d='M326 255c86 0 65 95 5 73' fill='none' stroke='{0}' stroke-width='12' stroke-linecap='round'/><rect x='260' y='319' width='22' height='33' rx='4' fill='{1}'/>".format(primary, secondary) if cable else ""
    return f"""<rect x='171' y='96' width='153' height='168' rx='28' fill='{primary}'/>
      <rect x='211' y='62' width='19' height='40' rx='6' fill='#64748b'/><rect x='266' y='62' width='19' height='40' rx='6' fill='#64748b'/>
      <rect x='215' y='148' width='89' height='53' rx='10' fill='{secondary}'/><path d='M260 159v30m-15-15h30' stroke='#fff' stroke-width='8' stroke-linecap='round'/>{cable_path}"""


def _powerbank(primary, secondary):
    return f"""<rect x='160' y='86' width='200' height='213' rx='30' fill='{primary}'/>
      <rect x='197' y='120' width='126' height='87' rx='16' fill='{secondary}'/><path d='M254 142l-25 38h24l-8 30 31-43h-23z' fill='#fff'/>
      <circle cx='219' cy='248' r='8' fill='#fff'/><circle cx='247' cy='248' r='8' fill='#fff'/><circle cx='275' cy='248' r='8' fill='#fff'/>"""


def _cable(primary, secondary):
    return f"""<path d='M109 204c0-91 120-92 147-23 25 63 101 61 126 1' fill='none' stroke='{primary}' stroke-width='21' stroke-linecap='round'/>
      <rect x='86' y='187' width='48' height='38' rx='8' fill='#334155'/><rect x='367' y='164' width='54' height='47' rx='8' fill='#334155'/>
      <path d='M123 197h27m227-13h31' stroke='{secondary}' stroke-width='9'/>"""


def _laptop(primary, secondary):
    return f"""<rect x='135' y='73' width='250' height='168' rx='13' fill='{primary}'/><rect x='150' y='88' width='220' height='137' rx='7' fill='{secondary}' opacity='.82'/>
      <path d='M95 255h330l-34 51H129z' fill='#334155'/><path d='M165 268h190l-11 20H176z' fill='#e2e8f0'/>"""


def _keyboard(primary, secondary):
    keys = ''.join(f"<rect x='{142 + (i % 8) * 31}' y='{124 + (i // 8) * 34}' width='23' height='23' rx='4' fill='{secondary}' opacity='.9'/>" for i in range(24))
    return f"<rect x='113' y='99' width='294' height='163' rx='22' fill='{primary}'/>{keys}<rect x='202' y='226' width='116' height='19' rx='5' fill='#fff' opacity='.78'/>"


def _mouse(primary, secondary):
    return f"""<path d='M260 58c-71 0-108 62-108 139 0 86 43 137 108 137s108-51 108-137c0-77-37-139-108-139z' fill='{primary}'/>
      <path d='M260 58v103' stroke='{secondary}' stroke-width='10'/><rect x='247' y='111' width='26' height='43' rx='13' fill='#fff' opacity='.84'/>"""


def _router(primary, secondary):
    return f"""<rect x='112' y='192' width='296' height='87' rx='20' fill='{primary}'/><path d='M164 192V96m192 96V96' stroke='{primary}' stroke-width='14' stroke-linecap='round'/>
      <circle cx='181' cy='237' r='8' fill='{secondary}'/><circle cx='211' cy='237' r='8' fill='{secondary}'/><circle cx='241' cy='237' r='8' fill='{secondary}'/>"""


def _controller(primary, secondary):
    return f"""<path d='M124 189c5-52 45-82 91-65l45 17 45-17c46-17 86 13 91 65l10 85c3 28-28 40-47 20l-40-42h-118l-40 42c-19 20-50 8-47-20z' fill='{primary}'/>
      <path d='M189 182v45m-22-22h44' stroke='#fff' stroke-width='10' stroke-linecap='round'/><circle cx='331' cy='188' r='10' fill='{secondary}'/><circle cx='358' cy='214' r='10' fill='{secondary}'/>"""


def _airfryer(primary, secondary):
    return f"""<rect x='154' y='57' width='212' height='278' rx='46' fill='{primary}'/><rect x='195' y='91' width='130' height='62' rx='14' fill='{secondary}'/>
      <circle cx='260' cy='122' r='18' fill='#fff' opacity='.82'/><path d='M190 213h140v82c0 17-14 30-30 30h-80c-16 0-30-13-30-30z' fill='#1f2937'/><rect x='225' y='232' width='70' height='15' rx='7' fill='{secondary}'/>"""


def _kettle(primary, secondary):
    return f"""<path d='M166 166c0-61 43-102 96-102 59 0 104 44 104 111v78c0 48-42 83-100 83-59 0-100-35-100-83z' fill='{primary}'/>
      <path d='M365 159c53 10 58 90 3 109' fill='none' stroke='{primary}' stroke-width='20'/><path d='M175 127h162' stroke='{secondary}' stroke-width='17' stroke-linecap='round'/><circle cx='257' cy='194' r='14' fill='#fff' opacity='.8'/>"""


def _appliance(primary, secondary, kind="washer"):
    if kind == "fan":
        return f"""<circle cx='260' cy='158' r='92' fill='{primary}'/><circle cx='260' cy='158' r='22' fill='{secondary}'/>
          <path d='M260 136c-16-70 20-83 41-58 15 19-6 52-41 58m21 22c66-28 84 6 61 33-18 20-55-1-61-33m-20 18c26 66-8 84-35 62-19-16 0-56 35-62m-17-20c-70 16-83-20-58-41 19-15 52 6 58 41' fill='{secondary}'/><path d='M260 250v83m-54 0h108' stroke='#334155' stroke-width='17' stroke-linecap='round'/>"""
    return f"""<rect x='155' y='47' width='210' height='288' rx='23' fill='{primary}'/><rect x='180' y='75' width='160' height='72' rx='12' fill='{secondary}' opacity='.8'/>
      <circle cx='260' cy='245' r='55' fill='#f8fafc'/><circle cx='260' cy='245' r='39' fill='#1f2937'/><circle cx='260' cy='245' r='7' fill='{secondary}'/>
      <circle cx='216' cy='107' r='8' fill='#fff'/><circle cx='242' cy='107' r='8' fill='#fff'/><circle cx='268' cy='107' r='8' fill='#fff'/>"""


def _brakepad(primary, secondary):
    return f"""<circle cx='260' cy='190' r='112' fill='{primary}'/><circle cx='260' cy='190' r='80' fill='{secondary}'/><circle cx='260' cy='190' r='37' fill='#f8fafc'/>
      <path d='M113 246l90-35 29 48-95 35zM407 134l-90 35-29-48 95-35z' fill='#334155'/><circle cx='260' cy='190' r='11' fill='#64748b'/>"""


def _filter(primary, secondary):
    return f"""<ellipse cx='260' cy='104' rx='87' ry='27' fill='{secondary}'/><rect x='173' y='104' width='174' height='178' fill='{primary}'/>
      <ellipse cx='260' cy='282' rx='87' ry='27' fill='{primary}'/><path d='M194 122v142m27-151v162m27-168v170m27-170v170m27-164v162m27-153v142' stroke='{secondary}' stroke-width='8' opacity='.9'/>"""


def _sparkplug(primary, secondary):
    return f"""<path d='M236 49h48v70h29v71h-17v57h-72v-57h-17v-71h29z' fill='{primary}'/>
      <path d='M236 119h48m-48 25h48m-48 25h48' stroke='{secondary}' stroke-width='8'/><path d='M244 247v59m32-59v59' stroke='#334155' stroke-width='10'/>"""


def _wiper(primary, secondary):
    return f"""<path d='M115 257l282-117' stroke='{primary}' stroke-width='24' stroke-linecap='round'/><path d='M135 236l242-100' stroke='{secondary}' stroke-width='8'/>
      <path d='M260 195l28 69' stroke='#334155' stroke-width='16' stroke-linecap='round'/>"""


def _dashcam(primary, secondary):
    return f"""<rect x='133' y='128' width='254' height='136' rx='27' fill='{primary}'/><circle cx='260' cy='196' r='52' fill='#17213c'/><circle cx='260' cy='196' r='34' fill='{secondary}'/>
      <rect x='213' y='88' width='94' height='40' rx='12' fill='#334155'/><path d='M260 88V59' stroke='#334155' stroke-width='13' stroke-linecap='round'/>"""


def _inflator(primary, secondary):
    return f"""<rect x='164' y='111' width='192' height='183' rx='33' fill='{primary}'/><circle cx='260' cy='179' r='42' fill='#fff'/><circle cx='260' cy='179' r='31' fill='{secondary}'/>
      <path d='M356 242c83 0 80 87 25 89' fill='none' stroke='{primary}' stroke-width='12'/><path d='M195 284h130' stroke='#334155' stroke-width='16'/>"""


def _seatcover(primary, secondary):
    return f"""<path d='M193 65h92c31 0 53 22 53 53v78c0 28-14 48-38 62l22 77H178l22-77c-24-14-38-34-38-62v-78c0-31 22-53 31-53z' fill='{primary}'/>
      <path d='M193 150h134m-121 111h108' stroke='{secondary}' stroke-width='12' opacity='.85'/>"""


def _cookware(primary, secondary):
    return f"""<circle cx='230' cy='210' r='89' fill='{primary}'/><circle cx='230' cy='210' r='65' fill='{secondary}'/><path d='M310 190h106' stroke='{primary}' stroke-width='29' stroke-linecap='round'/>
      <path d='M186 123l-16-46h120l-16 46' fill='{primary}'/><circle cx='230' cy='210' r='13' fill='#fff' opacity='.75'/>"""


def _bottle(primary, secondary):
    return f"""<rect x='213' y='66' width='94' height='36' rx='9' fill='#334155'/><path d='M205 101h110v43c0 16 27 31 27 67v82c0 31-25 54-54 54h-56c-29 0-54-23-54-54v-82c0-36 27-51 27-67z' fill='{primary}'/>
      <rect x='190' y='187' width='140' height='65' rx='14' fill='{secondary}' opacity='.8'/>"""


def _knife(primary, secondary):
    return f"""<path d='M111 126c78-23 177-19 240 12l-95 95c-31-61-86-88-145-107z' fill='{secondary}'/>
      <path d='M256 233l101 102c14 14 37-7 23-23L279 211z' fill='{primary}'/><circle cx='306' cy='283' r='7' fill='#fff'/>"""


def _shoe(primary, secondary):
    return f"""<path d='M108 243c50-5 90-45 122-111l52 26c-10 40 20 58 72 66 39 6 66 27 66 58v29H108z' fill='{primary}'/>
      <path d='M164 244c43-18 68-52 82-92' stroke='{secondary}' stroke-width='17' fill='none' stroke-linecap='round'/><path d='M108 310h312' stroke='#334155' stroke-width='13'/>"""


def _backpack(primary, secondary):
    return f"""<path d='M176 130c0-56 37-87 84-87s84 31 84 87v204H176z' fill='{primary}'/><path d='M215 130v-18c0-31 18-49 45-49s45 18 45 49v18' fill='none' stroke='{secondary}' stroke-width='13'/>
      <rect x='199' y='190' width='122' height='93' rx='17' fill='{secondary}' opacity='.76'/><path d='M260 214v44' stroke='#fff' stroke-width='9'/>"""


def _watch(primary, secondary):
    return f"""<rect x='221' y='42' width='78' height='78' rx='18' fill='{primary}'/><rect x='221' y='270' width='78' height='78' rx='18' fill='{primary}'/>
      <rect x='176' y='99' width='168' height='192' rx='40' fill='{primary}'/><rect x='194' y='120' width='132' height='148' rx='26' fill='{secondary}'/>
      <path d='M260 145v51l31 18' stroke='#fff' stroke-width='9' stroke-linecap='round' fill='none'/>"""


def _racket(primary, secondary):
    return f"""<ellipse cx='235' cy='151' rx='84' ry='107' fill='none' stroke='{primary}' stroke-width='23'/><path d='M180 95l110 110m0-110L180 205m-26-54h162m-81-88v176' stroke='{secondary}' stroke-width='5'/>
      <path d='M264 242l49 102' stroke='{primary}' stroke-width='23' stroke-linecap='round'/><path d='M311 337l20 40' stroke='#334155' stroke-width='29' stroke-linecap='round'/>"""


def _ball(primary, secondary):
    return f"""<circle cx='260' cy='191' r='121' fill='{primary}'/><path d='M139 191h242M260 70c35 37 52 77 52 121s-17 84-52 121M260 70c-35 37-52 77-52 121s17 84 52 121' fill='none' stroke='{secondary}' stroke-width='10'/>"""


def _tent(primary, secondary):
    return f"""<path d='M94 302L260 72l166 230z' fill='{primary}'/><path d='M260 72v230M160 302l100-150 100 150' fill='none' stroke='{secondary}' stroke-width='10'/><path d='M226 302v-59c0-18 15-32 34-32s34 14 34 32v59z' fill='#1e293b'/>"""


def _printer(primary, secondary):
    return f"""<rect x='143' y='146' width='234' height='156' rx='24' fill='{primary}'/><rect x='184' y='55' width='152' height='116' rx='9' fill='#fff'/><path d='M204 86h112m-112 25h112' stroke='{secondary}' stroke-width='8'/>
      <rect x='186' y='228' width='148' height='92' rx='9' fill='#fff'/><circle cx='334' cy='181' r='8' fill='{secondary}'/>"""


def _calculator(primary, secondary):
    buttons = ''.join(f"<rect x='{190 + (i % 4) * 38}' y='{154 + (i // 4) * 37}' width='26' height='26' rx='5' fill='{secondary}'/>" for i in range(16))
    return f"<rect x='163' y='42' width='194' height='299' rx='22' fill='{primary}'/><rect x='190' y='79' width='140' height='52' rx='7' fill='#dff9e7'/>{buttons}"


def _notebook(primary, secondary):
    return f"""<rect x='157' y='55' width='204' height='281' rx='11' fill='{primary}'/><path d='M195 55v281' stroke='{secondary}' stroke-width='13'/><path d='M219 121h105m-105 35h105m-105 35h105m-105 35h105m-105 35h105' stroke='#fff' stroke-width='7' opacity='.82'/>"""


def _office_chair(primary, secondary):
    return f"""<path d='M174 67h172v138c0 45-34 78-86 78s-86-33-86-78z' fill='{primary}'/><rect x='199' y='231' width='122' height='52' rx='13' fill='{secondary}'/><path d='M260 283v64m-74 0h148M260 347l-59 28m59-28l59 28' stroke='#334155' stroke-width='14' stroke-linecap='round'/>"""


def _tripod(primary, secondary):
    return f"""<rect x='211' y='66' width='98' height='75' rx='13' fill='{primary}'/><circle cx='260' cy='103' r='24' fill='{secondary}'/>
      <path d='M260 141v76m0 0l-96 125m96-125l96 125' stroke='{primary}' stroke-width='18' stroke-linecap='round'/><path d='M212 341h96' stroke='#334155' stroke-width='13' stroke-linecap='round'/>"""


def _tracker(primary, secondary):
    return f"""<rect x='156' y='102' width='208' height='188' rx='48' fill='{primary}'/><circle cx='260' cy='196' r='58' fill='{secondary}'/><circle cx='260' cy='196' r='25' fill='#fff'/><path d='M260 139v114m-57-57h114' stroke='#fff' stroke-width='8' opacity='.86'/>"""


def _headlight(primary, secondary):
    return f"""<path d='M116 125c78-53 181-53 263 6v143c-82 59-185 59-263 6z' fill='{primary}'/><ellipse cx='255' cy='199' rx='93' ry='75' fill='#1e293b'/><ellipse cx='255' cy='199' rx='67' ry='51' fill='{secondary}'/><path d='M387 151l46-26m-46 67h54m-54 41l46 26' stroke='{secondary}' stroke-width='10' stroke-linecap='round'/>"""


def _rack(primary, secondary):
    return f"""<path d='M151 82v230m218-230v230M118 131h284M118 202h284M118 273h284' stroke='{primary}' stroke-width='17' stroke-linecap='round'/><path d='M172 131v142m58-142v142m58-142v142m58-142v142' stroke='{secondary}' stroke-width='8'/>"""


def _cosmetic(primary, secondary):
    return f"""<rect x='182' y='68' width='75' height='57' rx='11' fill='#334155'/><path d='M171 122h97v187c0 21-17 38-38 38h-21c-21 0-38-17-38-38z' fill='{primary}'/><rect x='285' y='139' width='70' height='168' rx='13' fill='{secondary}'/><path d='M297 139v-38h46v38' fill='#334155'/><circle cx='220' cy='210' r='19' fill='#fff' opacity='.8'/>"""


def _dryer(primary, secondary):
    return f"""<path d='M122 145c0-54 44-87 102-87h89c43 0 75 35 75 78 0 44-33 78-75 78h-51l42 91-67 29-52-120h-61c-45 0-82-30-82-69z' fill='{primary}'/><circle cx='307' cy='136' r='36' fill='{secondary}'/><path d='M134 133l-50-25m50 55H75m59 28l-50 25' stroke='{secondary}' stroke-width='10' stroke-linecap='round'/>"""


def _apparel(primary, secondary):
    return f"""<path d='M176 83l42 25h84l42-25 75 54-45 86-42-24v143H188V199l-42 24-45-86z' fill='{primary}'/><path d='M218 108c5 36 79 36 84 0' fill='none' stroke='{secondary}' stroke-width='10'/><path d='M218 181h84' stroke='{secondary}' stroke-width='8' opacity='.8'/>"""


def _sunglasses(primary, secondary):
    return f"""<path d='M104 157h120c12 0 22 10 22 22v21c0 50-97 50-97 0v-16h-45zm312 0H296c-12 0-22 10-22 22v21c0 50 97 50 97 0v-16h45z' fill='{primary}'/><path d='M246 177c8-16 20-16 28 0' stroke='{secondary}' stroke-width='10' fill='none'/><path d='M149 168l-55-28m277 28l55-28' stroke='{primary}' stroke-width='13'/>"""


def _mat(primary, secondary):
    return f"""<rect x='111' y='116' width='298' height='161' rx='71' fill='{primary}'/><rect x='132' y='139' width='256' height='115' rx='53' fill='{secondary}' opacity='.75'/><path d='M155 170h210m-210 34h210m-210 34h210' stroke='#fff' stroke-width='6' opacity='.6'/>"""


def _box_set(primary, secondary):
    return f"""<rect x='127' y='136' width='252' height='176' rx='16' fill='{primary}'/><path d='M127 136l126-64 126 64-126 66z' fill='{secondary}'/><path d='M253 202v110' stroke='#fff' stroke-width='8' opacity='.75'/><path d='M161 154l92 48 92-48' fill='none' stroke='#fff' stroke-width='8' opacity='.75'/>"""


def _silhouette(product, primary, secondary, view):
    """Choose a recognisable silhouette from the exact catalog product type."""
    kind = str(product.get("product_type", "")).lower()
    category = str(product.get("category", ""))
    if "headphone" in kind or "earbud" in kind or "headset" in kind:
        art = _headphones(primary, secondary)
    elif "soundbar" in kind:
        art = _speaker(primary, secondary, soundbar=True)
    elif "speaker" in kind or "theatre" in kind:
        art = _speaker(primary, secondary)
    elif "camera" in kind or "webcam" in kind:
        art = _camera(primary, secondary)
    elif "tv" in kind or "monitor" in kind or "projector" in kind:
        art = _screen(primary, secondary, stand="projector" not in kind)
    elif "phone case" in kind:
        art = _phone(primary, secondary, "case")
    elif "charging stand" in kind:
        art = _phone(primary, secondary, "stand")
    elif "phone mount" in kind or "phone holder" in kind:
        art = _phone(primary, secondary, "mount")
    elif "power bank" in kind:
        art = _powerbank(primary, secondary)
    elif "bluetooth tracker" in kind:
        art = _tracker(primary, secondary)
    elif "tripod" in kind:
        art = _tripod(primary, secondary)
    elif "tempered glass" in kind:
        art = _phone(primary, secondary)
    elif "charger" in kind:
        art = _charger(primary, secondary)
    elif "cable" in kind:
        art = _cable(primary, secondary)
    elif "laptop" in kind or "sleeve" in kind:
        art = _laptop(primary, secondary)
    elif "keyboard" in kind:
        art = _keyboard(primary, secondary)
    elif "mouse" in kind:
        art = _mouse(primary, secondary)
    elif "router" in kind or "dock" in kind or "ssd" in kind:
        art = _router(primary, secondary)
    elif "controller" in kind:
        art = _controller(primary, secondary)
    elif "air fryer" in kind:
        art = _airfryer(primary, secondary)
    elif "kettle" in kind or "coffee maker" in kind or "mixer" in kind:
        art = _kettle(primary, secondary)
    elif "fan" in kind:
        art = _appliance(primary, secondary, "fan")
    elif any(word in kind for word in ("washer", "vacuum", "purifier", "microwave", "oven")):
        art = _appliance(primary, secondary)
    elif "brake pad" in kind:
        art = _brakepad(primary, secondary)
    elif "filter" in kind or "bearing" in kind or "fuel pump" in kind:
        art = _filter(primary, secondary)
    elif "spark plug" in kind:
        art = _sparkplug(primary, secondary)
    elif any(word in kind for word in ("wiper", "belt", "cable", "shock")) and category == "Automotive Parts":
        art = _wiper(primary, secondary)
    elif "dash" in kind or "reverse camera" in kind or "stereo" in kind:
        art = _dashcam(primary, secondary)
    elif "headlight" in kind:
        art = _headlight(primary, secondary)
    elif "inflator" in kind or "vacuum cleaner" in kind:
        art = _inflator(primary, secondary)
    elif "seat cover" in kind:
        art = _seatcover(primary, secondary)
    elif "roof carrier" in kind:
        art = _rack(primary, secondary)
    elif "car care" in kind:
        art = _box_set(primary, secondary)
    elif any(word in kind for word in ("cookware", "cooktop", "chopper", "knife")):
        art = _knife(primary, secondary) if "knife" in kind else _cookware(primary, secondary)
    elif "rack" in kind or "lamp" in kind:
        art = _rack(primary, secondary)
    elif any(word in kind for word in ("bottle", "flask", "container", "scale")):
        art = _bottle(primary, secondary)
    elif "shoe" in kind:
        art = _shoe(primary, secondary)
    elif "backpack" in kind or "wallet" in kind:
        art = _backpack(primary, secondary)
    elif "watch" in kind or "tracker" in kind:
        art = _watch(primary, secondary)
    elif "sunglasses" in kind:
        art = _sunglasses(primary, secondary)
    elif "hair dryer" in kind:
        art = _dryer(primary, secondary)
    elif any(word in kind for word in ("skin care", "fragrance", "makeup")):
        art = _cosmetic(primary, secondary)
    elif "t-shirt" in kind:
        art = _apparel(primary, secondary)
    elif "racket" in kind or "bat" in kind or "band" in kind:
        art = _racket(primary, secondary)
    elif "football" in kind or "helmet" in kind:
        art = _ball(primary, secondary)
    elif "yoga mat" in kind:
        art = _mat(primary, secondary)
    elif "tent" in kind or "jacket" in kind:
        art = _tent(primary, secondary)
    elif "printer" in kind or "scanner" in kind or "label maker" in kind:
        art = _printer(primary, secondary)
    elif "calculator" in kind or "stapler" in kind or "pen" in kind:
        art = _calculator(primary, secondary)
    elif "notebook" in kind or "organiser" in kind or "cartridge" in kind:
        art = _notebook(primary, secondary)
    elif "chair" in kind:
        art = _office_chair(primary, secondary)
    else:
        # Sensible category fallback for any future product type.
        art = _screen(primary, secondary) if category in {"Electronics", "Computers & Gaming"} else _notebook(primary, secondary)
    return f"<g transform='{_transform(view)}'>{art}</g>"


def product_visual_svg(product, view="front", alt=""):
    """Return a data-URI SVG, with a product-type-specific silhouette."""
    primary, secondary, background = _palette(product)
    title = html.escape(str(product.get("product_type", product.get("title", "Product")))[:36])
    label = {"front": "FRONT VIEW", "angle": "ANGLED VIEW", "detail": "DETAIL VIEW"}.get(view, "PRODUCT VIEW")
    detail_note = "CLOSE PRODUCT DETAIL" if view == "detail" else "GENERATED CATALOG VISUAL"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="520" height="390" viewBox="0 0 520 390" role="img" aria-label="{html.escape(alt or title)}">
      <defs><filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="12" stdDeviation="12" flood-color="#373064" flood-opacity=".22"/></filter>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff"/><stop offset="1" stop-color="{background}"/></linearGradient></defs>
      <rect width="520" height="390" rx="26" fill="url(#bg)"/><ellipse cx="260" cy="334" rx="142" ry="20" fill="#4c416b" opacity=".15"/>
      <g filter="url(#shadow)">{_silhouette(product, primary, secondary, view)}</g>
      <text x="28" y="42" font-family="Arial, sans-serif" font-size="13" font-weight="700" fill="#625a7e" letter-spacing="1.4">{label}</text>
      <text x="28" y="347" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="#30284d">{title}</text>
      <text x="28" y="369" font-family="Arial, sans-serif" font-size="10" font-weight="600" fill="#746b91" letter-spacing=".65">{detail_note}</text>
    </svg>'''
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def catalog_image_html(product, view="front", css_class="catalog-thumb"):
    src = product_visual_svg(product, view, product.get("title", "Catalog product"))
    alt = html.escape(str(product.get("title", "Catalog product")))
    return f'<img class="{css_class}" src="{src}" alt="{alt}"/>'
