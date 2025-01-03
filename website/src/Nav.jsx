import "./Nav.css";
import ramalamaLogo from "./assets/ramalama-logo-text-only.svg";

const Navbar = () => {
  return (
    <nav className="navbar">
      <div className="navbar-left">
        <a href="">
          <img className="logo" src={ramalamaLogo} alt="RamaLama Logo"></img>
        </a>
      </div>
      <div className="navbar-middle"></div>
      <div className="navbar-right">
        <ul className="nav-links">
          <li>
            <a href="#install">Install</a>
          </li>
          <li>
            <a href="#about">About</a>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default Navbar;
