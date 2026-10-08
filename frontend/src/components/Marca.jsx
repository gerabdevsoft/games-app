import logoRivero from "@/assets/logo-rivero-rector.jpeg";
import garraRivero from "@/assets/garra-rivero.png";
export function Garra({ clase = "" }) { return <img className={`imagen-garra ${clase}`} src={garraRivero} alt="Garra Rivero" />; }
export default function Marca() { return <div className="marca" data-testid="identidad-campana"><img className="logo-rivero" src={logoRivero} alt="Rivero Rector"/><div><strong>RIVERO RECTOR</strong><span>UNA UNIVERSIDAD LIBRE Y PARA TODOS</span></div></div>; }