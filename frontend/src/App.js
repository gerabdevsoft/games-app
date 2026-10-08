import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import "@/BrandOverrides.css";
import { ProveedorSesion, useSesion } from "@/context/SesionContext";
import Acceso from "@/pages/Acceso";
import Inicio from "@/pages/Inicio";
import Propuestas from "@/pages/Propuestas";
import Juegos from "@/pages/Juegos";
import Premios from "@/pages/Premios";
import Perfil from "@/pages/Perfil";
import Administracion from "@/pages/Administracion";
import Entregas from "@/pages/Entregas";
import UsuariosAdmin from "@/pages/UsuariosAdmin";
import PuntosCanje from "@/pages/PuntosCanje";
import PuntosCanjePublicos from "@/pages/PuntosCanjePublicos";

function RutaPrivada({ children }) { return useSesion().token ? children : <Navigate to="/acceso" />; }
export default function App() { return <BrowserRouter><ProveedorSesion><Routes><Route path="/acceso" element={<Acceso/>}/><Route path="/" element={<RutaPrivada><Inicio/></RutaPrivada>}/><Route path="/propuestas" element={<RutaPrivada><Propuestas/></RutaPrivada>}/><Route path="/juegos" element={<RutaPrivada><Juegos/></RutaPrivada>}/><Route path="/premios" element={<RutaPrivada><Premios/></RutaPrivada>}/><Route path="/puntos-canje" element={<RutaPrivada><PuntosCanjePublicos/></RutaPrivada>}/><Route path="/perfil" element={<RutaPrivada><Perfil/></RutaPrivada>}/><Route path="/administracion" element={<RutaPrivada><Administracion/></RutaPrivada>}/><Route path="/administracion/entregas" element={<RutaPrivada><Entregas/></RutaPrivada>}/><Route path="/administracion/usuarios" element={<RutaPrivada><UsuariosAdmin/></RutaPrivada>}/><Route path="/administracion/puntos-canje" element={<RutaPrivada><PuntosCanje/></RutaPrivada>}/><Route path="*" element={<Navigate to="/"/>}/></Routes><Toaster richColors position="top-center"/></ProveedorSesion></BrowserRouter>; }