// SPDX-License-Identifier: MIT
pragma solidity 0.8.36;

import {OriginWallet, PrincipalWallet, OriginPhishingContract} from "../src/OriginAuthDemo.sol";

interface Vm {
    function deal(address account, uint256 newBalance) external;
    function startPrank(address msgSender, address txOrigin) external;
    function stopPrank() external;
    function expectRevert(bytes calldata reason) external;
}

contract OriginAuthDemoTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address private constant OWNER = address(0x1001);
    address private constant ATTACKER = address(0x2002);

    function testOriginWalletIsDrainedThroughIntermediateContract() external {
        vm.startPrank(OWNER, OWNER);
        OriginWallet wallet = new OriginWallet();
        vm.stopPrank();

        OriginPhishingContract phishing = new OriginPhishingContract();
        vm.deal(address(wallet), 1 ether);

        vm.startPrank(ATTACKER, OWNER);
        phishing.drain(wallet, 1 ether);
        vm.stopPrank();

        require(address(phishing).balance == 1 ether, "drain did not succeed");
        require(address(wallet).balance == 0, "wallet still funded");
    }

    function testExplicitPrincipalRejectsIntermediateContract() external {
        vm.startPrank(OWNER, OWNER);
        PrincipalWallet wallet = new PrincipalWallet();
        vm.stopPrank();

        OriginPhishingContract phishing = new OriginPhishingContract();
        vm.deal(address(wallet), 1 ether);

        vm.startPrank(ATTACKER, OWNER);
        vm.expectRevert(bytes("principal owner"));
        phishing.drainPrincipal(wallet, 1 ether);
        vm.stopPrank();

        require(address(phishing).balance == 0, "safe wallet paid phishing contract");
        require(address(wallet).balance == 1 ether, "safe wallet lost funds");
    }
}
