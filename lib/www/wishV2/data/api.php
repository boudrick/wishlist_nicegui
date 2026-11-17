<?php
error_reporting(0);
define('DATA_DIR', __DIR__ . '/data/');

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') exit(0);

function ok($d=[])  { echo json_encode(['ok'=>true]+$d);  exit; }
function err($msg)  { echo json_encode(['ok'=>false,'err'=>$msg]); exit; }
function slug($s)   { return preg_replace('/[^a-z0-9\-]/','',strtolower($s)); }
function path($s)   { return DATA_DIR.slug($s).'.json'; }
function load($s)   { $p=path($s); return file_exists($p) ? json_decode(file_get_contents($p),true) : null; }
function save($d)   { file_put_contents(DATA_DIR.slug($d['slug']).'.json', json_encode($d, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE)); }
function body()     { $d=json_decode(file_get_contents('php://input'),true); if(!$d) err('JSON invalide'); return $d; }
function darken($h,$a) {
    $r=hexdec(substr($h,1,2)); $g=hexdec(substr($h,3,2)); $b=hexdec(substr($h,5,2));
    return sprintf('#%02x%02x%02x',max(0,round($r*(1-$a))),max(0,round($g*(1-$a))),max(0,round($b*(1-$a))));
}

$action = $_GET['action'] ?? '';

try { switch($action) {

    case 'reserve':
        $b=body(); $p=load($b['slug']??''); if(!$p) err('Personne introuvable');
        $name=trim($b['name']??'')?:'Anonyme';
        foreach($p['elements'] as &$e) {
            if($e['type']!=='cadeau'||$e['id']!=$b['id']) continue;
            if($e['multiple']) {
                if(!$e['unlimited']&&$e['reserved_count']>=$e['max_quantity']) err('Quantité max atteinte');
                $e['reserved_count']++; $e['participants'][]=$name;
            } else {
                if($e['statut']==='pris') err('Déjà réservé');
                $e['statut']='pris'; $e['reserve_par']=$name;
            }
            save($p); ok();
        }
        err('Cadeau introuvable');

    case 'cancel':
        $b=body(); $p=load($b['slug']??''); if(!$p) err('Personne introuvable');
        $name=trim($b['name']??'')?:'Anonyme';
        foreach($p['elements'] as &$e) {
            if($e['type']!=='cadeau'||$e['id']!=$b['id']) continue;
            if($e['multiple']) {
                $i=array_search($name,$e['participants']??[]);
                if($i!==false){array_splice($e['participants'],$i,1);$e['reserved_count']=count($e['participants']);}
            } else {
                if($e['reserve_par']!==$name) err("Ce n'est pas votre réservation");
                $e['statut']='libre'; $e['reserve_par']='';
            }
            save($p); ok();
        }
        err('Cadeau introuvable');

    case 'save':
        $b=body(); $p=load($b['slug']??''); if(!$p) err('Introuvable');
        if(($b['admin_code']??'')!==$p['admin_code']) err('Code incorrect');
        if(isset($b['elements'])) $p['elements']=$b['elements'];
        foreach(['nom','emoji','description','avatar','theme'] as $f) if(isset($b[$f])) $p[$f]=$b[$f];
        save($p); ok();

    case 'create':
        $b=body();
        $s=slug($b['slug']??''); if(!$s) err('Slug invalide');
        if(file_exists(path($s))) err('Cette personne existe déjà');
        if(strlen($b['admin_code']??'')<4) err('Code trop court (min 4 car.)');
        $c=$b['color']??'#1a6b3c'; $nom=trim($b['nom']??$s);
        save(['slug'=>$s,'nom'=>$nom,'emoji'=>$b['emoji']??'🎁','description'=>$b['description']??'',
            'avatar'=>'https://ui-avatars.com/api/?name='.urlencode($nom).'&background='.ltrim($c,'#').'&color=fff&size=200&bold=true',
            'theme'=>['primary'=>$c,'secondary'=>darken($c,.25),'accent'=>'#FFE135','gradient_start'=>$c,'gradient_end'=>darken($c,.6)],
            'admin_code'=>$b['admin_code'],'elements'=>[]]);
        ok(['slug'=>$s]);

    default: err('Action inconnue');

}} catch(Throwable $e){ err('Erreur serveur'); }
